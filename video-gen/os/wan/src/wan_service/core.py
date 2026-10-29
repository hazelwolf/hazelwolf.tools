"""Thin adapter over mlx-gen's Wan 2.2 TI2V-5B. Shared by the API and MCP server.

A clip takes ~10+ minutes on an M5 Max, longer than an MCP or HTTP client will wait, so callers submit a job and
poll it. One worker thread runs jobs in order (MLX runs one generation at a time on the GPU). Jobs live in memory.

Memory: the Wan 2.2 VAE decodes untiled (mlx-gen refuses spatial tiling for it), so decode memory grows with frame
area. Measured on a 48 GB M5 Max with the transformer released before decode: 23 GB at 832x480, 33 GB at 1024x576,
50 GB at 1280x704 (swaps). Frame area is therefore capped at 1024x576, and each job builds a fresh model (2-4 s)
because releasing the transformer leaves the old one unusable.
"""

from __future__ import annotations

import gc
import os
import queue
import random
import re
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from . import config

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_SIDE, MAX_SIDE = 256, 1024
MAX_AREA = 1024 * 576  # largest frame that decodes under the ~40 GB GPU working set (see module docstring)
FPS = 24  # TI2V-5B is trained at 24 fps
MAX_FRAMES = 121  # TI2V-5B's native maximum (~5 s)
MIN_DURATION_S, MAX_DURATION_S = 0.5, MAX_FRAMES / FPS
MIN_STEPS, MAX_STEPS = 4, 50
# mlx-gen's recommendation below 720p class (its default 5 is tuned for 1280x704, which does not fit here).
FLOW_SHIFT = 3.0


class ServiceError(Exception):
    """Error with an HTTP-ish status code, surfaced by both the API and MCP layers."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- model

_model_lock = threading.Lock()  # one generation on the GPU at a time


def _load_model():
    from mflux.models.common.config import ModelConfig
    from mflux.models.wan.variants import Wan2_2_TI2V

    from . import prepare

    # First use on a machine: download the package (~18 GB) before building the model.
    path = prepare.ensure_weights()
    model = Wan2_2_TI2V(model_path=str(path), model_config=ModelConfig.wan2_2_ti2v_5b())
    # mlx-gen caches prompt embeddings (skips reloading the 11 GB text encoder for a repeated prompt) under
    # ~/Library/Caches by default; keep them with the tool's other model files.
    store = getattr(model, "_prompt_embed_store", None)
    if store is not None and hasattr(store, "cache_dir"):
        store.cache_dir = config.MODELS_DIR / "prompt_embeds"
    return model


def _free_mlx():
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


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
    """Store an uploaded first-frame image under OUTPUT_DIR/inputs so a job can read it by path."""
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


# ---------------------------------------------------------------- generation


def frames_for(duration_s: float) -> int:
    """Nearest valid frame count (4k + 1, the VAE's temporal grid) for a duration at 24 fps, capped at 121."""
    return min(MAX_FRAMES, max(1, round(duration_s * FPS / 4)) * 4 + 1)


def _validate(prompt: str, width: int, height: int, duration_s: float, steps: int):
    if not prompt.strip():
        raise ServiceError("prompt is empty")
    for side, val in (("width", width), ("height", height)):
        if not MIN_SIDE <= val <= MAX_SIDE:
            raise ServiceError(f"{side} must be between {MIN_SIDE} and {MAX_SIDE}")
    if (width // 32 * 32) * (height // 32 * 32) > MAX_AREA:
        raise ServiceError(
            f"{width}x{height} is too large for this Mac's memory: keep width x height at or under 1024x576 "
            "(e.g. 1024x576, 576x1024, 768x768, 832x480)"
        )
    if not MIN_DURATION_S <= duration_s <= MAX_DURATION_S + 1e-6:
        raise ServiceError(f"duration_s must be between {MIN_DURATION_S:g} and {MAX_DURATION_S:.2f}")
    if not MIN_STEPS <= steps <= MAX_STEPS:
        raise ServiceError(f"steps must be between {MIN_STEPS} and {MAX_STEPS}")


def generate(
    prompt: str,
    width: int = 832,
    height: int = 480,
    duration_s: float = 5.0,
    steps: int | None = None,
    seed: int | None = None,
    image_path: str | None = None,
    negative_prompt: str | None = None,
    output_name: str | None = None,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Text-to-video (or image-to-video with image_path as the first frame). Blocks for the whole clip.

    Writes an MP4 (video only, no audio) into OUTPUT_DIR and returns its path. Width and height are rounded down
    to multiples of 32; with an image, mlx-gen fits the canvas to the image's aspect ratio near that size.
    """
    steps = steps or config.DEFAULT_STEPS
    _validate(prompt, width, height, duration_s, steps)
    width, height = width // 32 * 32, height // 32 * 32
    init = _input_image(image_path) if image_path else None
    seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    num_frames = frames_for(duration_s)

    def progress(event):
        if on_progress is not None:
            on_progress({"phase": event.phase, "step": event.step, "total_steps": event.total_steps})

    out = _reserve_output(output_name, ".mp4")
    model = video = None
    with _model_lock:
        try:
            if on_progress is not None:
                on_progress({"phase": "loading", "step": 0, "total_steps": steps})
            import mlx.core as mx

            t0 = time.perf_counter()
            model = _load_model()
            load_s = round(time.perf_counter() - t0, 1)
            mx.reset_peak_memory()
            t0 = time.perf_counter()
            video = model.generate_video(
                seed=seed,
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                width=width,
                height=height,
                num_frames=num_frames,
                fps=FPS,
                flow_shift=FLOW_SHIFT,
                image_path=str(init) if init else None,
                progress_callback=progress,
                # Free the transformer before the (untiled, memory-heavy) VAE decode, and flush MLX's cache each
                # step: together they cut peak memory by ~10 GB at 832x480.
                release_denoisers_before_decode=True,
                clear_cache_each_step=True,
            )
            if on_progress is not None:
                on_progress({"phase": "saving", "step": steps, "total_steps": steps})
            video.save(out, overwrite=True)  # the VAE decode runs here, streamed into the file
            out.chmod(0o644)  # mlx-gen writes through a private temp file (0600)
            elapsed = round(time.perf_counter() - t0, 1)
            peak_gb = round(mx.get_peak_memory() / 1024**3, 1)
            frames = getattr(video, "frame_count", None) or getattr(video, "_frame_count", num_frames)
            size = (video.width, video.height)
        except BaseException:
            out.unlink(missing_ok=True)
            raise
        finally:
            del model, video
            _free_mlx()
    return {
        "path": str(out),
        "name": out.name,
        "seed": seed,
        "width": size[0],
        "height": size[1],
        "fps": FPS,
        "frames": frames,
        "duration_s": round(frames / FPS, 2),
        "steps": steps,
        "audio": False,
        "generation_time_s": elapsed,
        "load_time_s": load_s,
        "peak_memory_gb": peak_gb,
    }


# ---------------------------------------------------------------- jobs

_jobs: OrderedDict[str, dict] = OrderedDict()
_jobs_lock = threading.Lock()
_jobs_changed = threading.Condition(_jobs_lock)
_queue: queue.Queue[str] = queue.Queue()
_worker: threading.Thread | None = None


def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def _update(job_id: str, **fields):
    with _jobs_changed:
        _jobs[job_id].update(fields)
        _jobs_changed.notify_all()


def _work_loop():
    while True:
        job_id = _queue.get()
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            continue
        _update(job_id, status="running", started_at=time.time())
        params = job["_params"]
        try:
            result = generate(
                **params,
                on_progress=lambda p, j=job_id: _update(
                    j, phase=p["phase"], step=p["step"], total_steps=p["total_steps"]
                ),
            )
            _update(job_id, status="done", phase="done", result=result, finished_at=time.time())
        except ServiceError as e:
            _update(job_id, status="failed", error=str(e), finished_at=time.time())
        except Exception as e:  # noqa: BLE001 - a failed job must not kill the worker
            _update(job_id, status="failed", error=f"{type(e).__name__}: {e}", finished_at=time.time())
        finally:
            upload = job.get("_cleanup")
            if upload:
                Path(upload).unlink(missing_ok=True)


def _ensure_worker():
    """Start the single worker. Caller holds _jobs_lock.

    The check and start must sit in the same critical section as the queue insert. Otherwise two
    first requests can each pass the `_worker is None` check, pull different jobs, and compete for
    `_model_lock` — clips run out of order, and a job shows "running" while it waits for the GPU.
    """
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_work_loop, name="wan-worker", daemon=True)
        _worker.start()


def submit(cleanup_path: str | None = None, **params) -> dict:
    """Validate and queue a clip. Returns the job at once; poll get_job for progress and the result."""
    steps = params.get("steps") or config.DEFAULT_STEPS
    _validate(
        params["prompt"], params.get("width", 832), params.get("height", 480), params.get("duration_s", 5.0), steps
    )
    if params.get("image_path"):
        _input_image(params["image_path"])
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "status": "queued",
        "phase": "queued",
        "step": 0,
        "total_steps": steps,
        "created_at": time.time(),
        "prompt": params["prompt"][:200],
        "result": None,
        "error": None,
        "_params": params,
        "_cleanup": cleanup_path,
    }
    with _jobs_changed:
        _jobs[job_id] = job
        while len(_jobs) > config.MAX_JOBS:
            oldest = next(iter(_jobs))
            if _jobs[oldest]["status"] in ("queued", "running"):
                break
            _jobs.pop(oldest)
        position = sum(1 for j in _jobs.values() if j["status"] in ("queued", "running")) - 1
        _ensure_worker()
        _queue.put(job_id)
    return {**_public(job), "queue_position": position}


def get_job(job_id: str, wait_s: float = 0.0) -> dict:
    """Current state of a job. With wait_s > 0, block up to that long until it finishes (or fails)."""
    deadline = time.monotonic() + max(0.0, min(wait_s, 300.0))
    with _jobs_changed:
        job = _jobs.get(job_id)
        if job is None:
            raise ServiceError(f"Unknown job: {job_id} (jobs are kept in memory; a restart clears them)", status=404)
        # Hold the dict object: submit() may evict finished jobs from _jobs while we wait.
        while job["status"] in ("queued", "running"):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            _jobs_changed.wait(remaining)
        return _public(job)


def list_jobs() -> list[dict]:
    with _jobs_lock:
        return [_public(j) for j in reversed(_jobs.values())]


def health() -> dict:
    from . import prepare

    with _jobs_lock:
        active = sum(1 for j in _jobs.values() if j["status"] in ("queued", "running"))
    return {
        "status": "ok",
        "model": config.HF_REPO,
        # False until the first job (or `wan-prepare`) downloads the package.
        "weights_ready": prepare.weights_ready(),
        "active_jobs": active,
        "default_steps": config.DEFAULT_STEPS,
        "max_size": "1024x576 (width x height area)",
        "output_dir": str(config.OUTPUT_DIR),
    }
