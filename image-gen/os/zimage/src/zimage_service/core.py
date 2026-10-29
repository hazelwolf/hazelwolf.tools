"""Thin adapter over mflux's MLX Z-Image-Turbo. Shared by the API and MCP server.

One model per process, loaded on first use and freed after ZIMAGE_IDLE_UNLOAD_S idle seconds. MLX runs one
generation at a time on the GPU, so requests are serialized with a lock.
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
MIN_SIDE, MAX_SIDE = 256, 2048
MAX_COUNT = 8


class ServiceError(Exception):
    """Error with an HTTP-ish status code, surfaced by both the API and MCP layers."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- model lifecycle

_lock = threading.Lock()
_model = None
_model_source: str | None = None
_last_used = 0.0
_load_time_s: float | None = None
_reaper: threading.Thread | None = None


def _load_model():
    import mlx.core as mx
    from mflux.models.common.config import ModelConfig
    from mflux.models.z_image import ZImage

    from . import prepare

    # First use on a machine: download from Hugging Face and save the quantized copy (~33 GB, minutes).
    source = str(prepare.ensure_weights())
    if config.MLX_CACHE_LIMIT_GB > 0:
        mx.set_cache_limit(int(config.MLX_CACHE_LIMIT_GB * 1024**3))
    # The saved copy already carries its quantization, so quantize is not passed again.
    model = ZImage(model_config=ModelConfig.z_image_turbo(), model_path=source)
    return model, source


def _free_mlx():
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


def _ensure_model():
    global _model, _model_source, _load_time_s
    if _model is None:
        t0 = time.perf_counter()
        _model, _model_source = _load_model()
        _load_time_s = round(time.perf_counter() - t0, 2)
        _start_reaper()
    return _model


def unload() -> dict:
    """Drop the model and return its memory to the system."""
    global _model, _model_source
    with _lock:
        was_loaded = _model is not None
        _model, _model_source = None, None
        _free_mlx()
    return {"unloaded": was_loaded}


def _reap_loop():
    global _model, _model_source
    while True:
        time.sleep(min(60.0, max(config.IDLE_UNLOAD_S / 4, 1.0)))
        if _model is None:
            return
        if time.monotonic() - _last_used >= config.IDLE_UNLOAD_S and _lock.acquire(blocking=False):
            try:
                if _model is not None and time.monotonic() - _last_used >= config.IDLE_UNLOAD_S:
                    _model, _model_source = None, None
                    _free_mlx()
                    return
            finally:
                _lock.release()


def _start_reaper():
    global _reaper
    if config.IDLE_UNLOAD_S > 0 and (_reaper is None or not _reaper.is_alive()):
        _reaper = threading.Thread(target=_reap_loop, name="zimage-idle-unload", daemon=True)
        _reaper.start()


# ---------------------------------------------------------------- files


def _reserve_output(name: str | None, suffix: str) -> Path:
    """Reserve a new file under OUTPUT_DIR with O_CREAT|O_EXCL so concurrent processes never share a path.

    An existing name is retried as -2, -3, ...
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-.")[:80]
    base = Path(stem).stem or f"image-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
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
    """Store an uploaded init image under OUTPUT_DIR/inputs so img2img can read it by path."""
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
    import platform

    from . import prepare

    return {
        "status": "ok",
        "model": config.HF_REPO,
        "model_path": str(config.MODEL_PATH),
        # False until the first generation (or `zimage-prepare`) downloads and quantizes the weights.
        "weights_ready": prepare.weights_ready(),
        "quantize": config.QUANTIZE,
        "loaded": _model is not None,
        "load_time_s": _load_time_s,
        "idle_unload_s": config.IDLE_UNLOAD_S,
        "device": "mlx-metal" if platform.system() == "Darwin" and platform.machine() == "arm64" else "mlx",
        "output_dir": str(config.OUTPUT_DIR),
    }


def _validate(prompt: str, width: int, height: int, steps: int, count: int, image_strength: float | None):
    if not prompt.strip():
        raise ServiceError("prompt is empty")
    for side, val in (("width", width), ("height", height)):
        if not MIN_SIDE <= val <= MAX_SIDE:
            raise ServiceError(f"{side} must be between {MIN_SIDE} and {MAX_SIDE}")
    if not 1 <= steps <= 50:
        raise ServiceError("steps must be between 1 and 50")
    if not 1 <= count <= MAX_COUNT:
        raise ServiceError(f"count must be between 1 and {MAX_COUNT}")
    if image_strength is not None and not 0.0 < image_strength < 1.0:
        raise ServiceError("image_strength must be between 0 and 1 (exclusive)")


def generate(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 9,
    seed: int | None = None,
    count: int = 1,
    image_path: str | None = None,
    image_strength: float | None = None,
    output_name: str | None = None,
) -> dict:
    """Text to image (or img2img with image_path). Writes PNGs into OUTPUT_DIR and returns their paths.

    Width and height are rounded down to multiples of 16. With count > 1, seeds run seed, seed+1, ...
    """
    global _last_used
    _validate(prompt, width, height, steps, count, image_strength)
    width, height = width // 16 * 16, height // 16 * 16
    init = _input_image(image_path) if image_path else None
    if init is not None and image_strength is None:
        image_strength = 0.4
    base_seed = seed if seed is not None else random.randint(0, 2**31 - 1)

    images = []
    with _lock:
        model = _ensure_model()
        try:
            for i in range(count):
                s = base_seed + i
                t0 = time.perf_counter()
                img = model.generate_image(
                    seed=s,
                    prompt=prompt,
                    num_inference_steps=steps,
                    width=width,
                    height=height,
                    image_path=str(init) if init else None,
                    image_strength=image_strength if init else None,
                )
                elapsed = round(time.perf_counter() - t0, 2)
                name = output_name if count == 1 or not output_name else f"{output_name}-s{s}"
                out = _reserve_output(name, ".png")
                try:
                    img.save(path=out, overwrite=True)
                except Exception:
                    out.unlink(missing_ok=True)
                    raise
                images.append({"path": str(out), "name": out.name, "seed": s, "generation_time_s": elapsed})
        finally:
            _last_used = time.monotonic()
            _free_mlx()
    return {
        "images": images,
        "width": width,
        "height": height,
        "steps": steps,
        "quantize": config.QUANTIZE,
        "load_time_s": _load_time_s,
    }
