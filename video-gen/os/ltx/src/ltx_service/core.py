"""Thin adapter over ltx-2-mlx's distilled LTX-2.5 pipeline. Shared by the API and MCP server.

One pipeline per process, created on first use and freed after LTX_IDLE_UNLOAD_S idle seconds. MLX runs one
generation at a time on the GPU, so requests are serialized with a lock. Upstream already frees the transformer
and decoders between clips (low_memory), so an idle pipeline holds little memory; the reaper drops the rest.
"""

from __future__ import annotations

import gc
import os
import random
import re
import threading
import time
import uuid
from pathlib import Path

from . import config

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_SIDE, MAX_SIDE = 256, 1920
MIN_DURATION_S, MAX_DURATION_S = 1.0, 20.0
FPS_CHOICES = (24.0, 25.0, 30.0)


class ServiceError(Exception):
    """Error with an HTTP-ish status code, surfaced by both the API and MCP layers."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- pipeline lifecycle

_lock = threading.Lock()
_pipe = None
_pack: str | None = None
_last_used = 0.0
_reaper: threading.Thread | None = None


def _load_pipeline():
    from ltx_pipelines_mlx import DistilledPipeline

    from . import prepare

    try:
        # First use on a machine: download the pack (~45 GB, gated) before building the pipeline.
        pack = str(prepare.ensure_weights())
    except prepare.WeightsUnavailable as e:
        raise ServiceError(str(e), status=503) from None
    return DistilledPipeline(model_dir=pack, low_memory=True, low_ram_streaming=config.LOW_RAM), pack


def _free_mlx():
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


def _ensure_pipeline():
    global _pipe, _pack
    if _pipe is None:
        _pipe, _pack = _load_pipeline()
        _start_reaper()
    return _pipe


def unload() -> dict:
    """Drop the pipeline and return its memory to the system."""
    global _pipe, _pack
    with _lock:
        was_loaded = _pipe is not None
        _pipe, _pack = None, None
        _free_mlx()
    return {"unloaded": was_loaded}


def _reap_loop():
    global _pipe, _pack
    while True:
        time.sleep(min(60.0, max(config.IDLE_UNLOAD_S / 4, 1.0)))
        if _pipe is None:
            return
        if time.monotonic() - _last_used >= config.IDLE_UNLOAD_S and _lock.acquire(blocking=False):
            try:
                if _pipe is not None and time.monotonic() - _last_used >= config.IDLE_UNLOAD_S:
                    _pipe, _pack = None, None
                    _free_mlx()
                    return
            finally:
                _lock.release()


def _start_reaper():
    global _reaper
    if config.IDLE_UNLOAD_S > 0 and (_reaper is None or not _reaper.is_alive()):
        _reaper = threading.Thread(target=_reap_loop, name="ltx-idle-unload", daemon=True)
        _reaper.start()


# ---------------------------------------------------------------- files


def _reserve_output(name: str | None, suffix: str) -> Path:
    """Reserve a new file under OUTPUT_DIR with O_CREAT|O_EXCL so concurrent processes never share a path.

    An existing name is retried as -2, -3, ...
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-.")[:80]
    base = Path(stem).stem or f"video-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    n = 0
    for _ in range(10_000):
        out = config.OUTPUT_DIR / (f"{base}{suffix}" if n == 0 else f"{base}-{n}{suffix}")
        try:
            os.close(os.open(out, flags, 0o644))
        except FileExistsError:
            n = 2 if n == 0 else n + 1
            continue
        return out
    raise ServiceError("could not allocate a unique output filename", status=500)


def _input_image(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.is_file():
        raise ServiceError(f"Image file not found: {p}", status=404)
    if p.suffix.lower() not in _IMAGE_SUFFIXES:
        raise ServiceError(f"Unsupported image type {p.suffix!r}; use one of {sorted(_IMAGE_SUFFIXES)}")
    if p.stat().st_size > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ServiceError(f"Image file exceeds {config.MAX_UPLOAD_MB} MB")
    return p


def save_upload(filename: str, raw: bytes) -> Path:
    """Store an uploaded first-frame image under OUTPUT_DIR/inputs so image-to-video can read it by path."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _IMAGE_SUFFIXES:
        raise ServiceError(f"Unsupported image type {suffix!r}; use one of {sorted(_IMAGE_SUFFIXES)}")
    inputs = config.OUTPUT_DIR / "inputs"
    inputs.mkdir(exist_ok=True)
    p = inputs / f"{uuid.uuid4().hex}{suffix}"
    p.write_bytes(raw)
    return p


def output_file(name: str) -> Path:
    p = (config.OUTPUT_DIR / name).resolve()
    if p.parent != config.OUTPUT_DIR.resolve() or not p.is_file():
        raise ServiceError(f"Output not found: {name}", status=404)
    return p


# ---------------------------------------------------------------- operations


def health() -> dict:
    from . import prepare

    return {
        "status": "ok",
        "model": config.HF_REPO,
        # False until the first generation (or `ltx-prepare`) downloads the gated pack.
        "weights_ready": prepare.weights_ready(),
        "hf_token_set": bool(os.environ.get("HF_TOKEN")),
        "loaded": _pipe is not None,
        "low_ram": config.LOW_RAM,
        "idle_unload_s": config.IDLE_UNLOAD_S,
        "output_dir": str(config.OUTPUT_DIR),
    }


def frames_for(duration_s: float, fps: float) -> int:
    """Nearest valid frame count (8k + 1, the VAE's causal grid) for a duration."""
    return max(1, round(duration_s * fps / 8)) * 8 + 1


def _validate(prompt: str, width: int, height: int, duration_s: float | None, fps: float):
    if not prompt.strip():
        raise ServiceError("prompt is empty")
    for side, val in (("width", width), ("height", height)):
        if not MIN_SIDE <= val <= MAX_SIDE:
            raise ServiceError(f"{side} must be between {MIN_SIDE} and {MAX_SIDE}")
    if duration_s is not None and not MIN_DURATION_S <= duration_s <= MAX_DURATION_S:
        raise ServiceError(f"duration_s must be between {MIN_DURATION_S:g} and {MAX_DURATION_S:g}")
    if fps not in FPS_CHOICES:
        raise ServiceError(f"fps must be one of {', '.join(f'{f:g}' for f in FPS_CHOICES)}")


def generate(
    prompt: str,
    width: int = 768,
    height: int = 512,
    duration_s: float | None = 5.0,
    fps: float = 24.0,
    seed: int | None = None,
    image_path: str | None = None,
    output_name: str | None = None,
) -> dict:
    """Text-to-video (or image-to-video with image_path as the first frame), with synchronized stereo audio.

    Writes an MP4 into OUTPUT_DIR and returns its path. Width and height are rounded down to multiples of 64.
    duration_s=None lets LTX-2.5 predict a length from the prompt (1-20 s).
    """
    global _last_used
    fps = float(fps)
    _validate(prompt, width, height, duration_s, fps)
    width, height = width // 64 * 64, height // 64 * 64
    init = _input_image(image_path) if image_path else None
    seed = seed if seed is not None else random.randint(0, 2**31 - 1)

    if duration_s is None:
        from ltx_pipelines_mlx.utils.types import AutoDuration

        num_frames = AutoDuration(MIN_DURATION_S, MAX_DURATION_S)
    else:
        num_frames = frames_for(duration_s, fps)

    out = _reserve_output(output_name, ".mp4")
    with _lock:
        try:
            pipe = _ensure_pipeline()
            import mlx.core as mx

            mx.reset_peak_memory()
            t0 = time.perf_counter()
            pipe.generate_and_save(
                prompt=prompt,
                output_path=str(out),
                height=height,
                width=width,
                num_frames=num_frames,
                frame_rate=fps,
                seed=seed,
                image=str(init) if init else None,
            )
            elapsed = round(time.perf_counter() - t0, 1)
            peak_gb = round(mx.get_peak_memory() / 1024**3, 1)
        except BaseException:
            out.unlink(missing_ok=True)
            raise
        finally:
            _last_used = time.monotonic()
            _free_mlx()
    frames = num_frames if isinstance(num_frames, int) else _probe_frames(out)
    return {
        "path": str(out),
        "name": out.name,
        "seed": seed,
        "width": width,
        "height": height,
        "fps": fps,
        "frames": frames,
        "duration_s": round(frames / fps, 2) if frames else None,
        "audio": True,
        "generation_time_s": elapsed,
        "peak_memory_gb": peak_gb,
    }


def _probe_frames(path: Path) -> int | None:
    """Frame count of an MP4 via ffprobe (only needed when the duration was auto-predicted)."""
    import shutil
    import subprocess

    if not shutil.which("ffprobe"):
        return None
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
         "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None
