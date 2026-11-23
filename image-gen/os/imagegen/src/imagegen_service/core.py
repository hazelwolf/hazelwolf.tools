"""Thin adapter over mflux's MLX Z-Image-Turbo and Boogu Image Turbo. Shared by the API and MCP server.

Z-Image is the default; Boogu is chosen per request (model="boogu") for text-heavy images. One model is held per
process, loaded on first use, swapped when a request asks for the other one (both at once would need ~41 GB), and
freed after IMAGEGEN_IDLE_UNLOAD_S idle seconds. Every MLX call
(load, generate, unload, cache clear) runs on one long-lived worker thread: MLX streams belong to the thread that
made them, and a model used from another thread fails with "There is no Stream(cpu, 0) in current thread". The
single worker also serializes requests, since MLX runs one generation at a time on the GPU.
"""

from __future__ import annotations

import gc
import os
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
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

_mlx = ThreadPoolExecutor(max_workers=1, thread_name_prefix="imagegen-mlx")
_model = None
_model_key: str | None = None
_model_source: str | None = None
_last_used = 0.0
_load_time_s: float | None = None
_reaper: threading.Thread | None = None


def _on_mlx(fn, *args, **kwargs):
    """Run fn on the MLX worker thread and wait for its result."""
    return _mlx.submit(fn, *args, **kwargs).result()


def _load_model(key: str):
    import mlx.core as mx

    from . import prepare

    # First use of a model on a machine: download from Hugging Face and save the quantized copy (tens of GB).
    source = str(prepare.ensure_weights(model=key))
    if config.MLX_CACHE_LIMIT_GB > 0:
        mx.set_cache_limit(int(config.MLX_CACHE_LIMIT_GB * 1024**3))
    cls, model_config = prepare.model_class(key)
    # The saved copy already carries its quantization, so quantize is not passed again.
    return cls(model_config=model_config, model_path=source), source


def _free_mlx():
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


def _ensure_model(key: str):
    global _model, _model_key, _model_source, _load_time_s
    if _model is not None and _model_key != key:
        _drop_model()
    if _model is None:
        t0 = time.perf_counter()
        _model, _model_source = _load_model(key)
        _model_key = key
        _load_time_s = round(time.perf_counter() - t0, 2)
        _start_reaper()
    return _model


def unload() -> dict:
    """Drop the model and return its memory to the system."""
    return {"unloaded": _on_mlx(_drop_model)}


def _drop_model(only_if_idle: bool = False) -> bool:
    global _model, _model_key, _model_source
    if _model is None or (only_if_idle and time.monotonic() - _last_used < config.IDLE_UNLOAD_S):
        return False
    _model, _model_key, _model_source = None, None, None
    _free_mlx()
    return True


def _reap_loop():
    while True:
        time.sleep(min(60.0, max(config.IDLE_UNLOAD_S / 4, 1.0)))
        if _model is None:
            return
        # Queued behind any running generation; idleness is checked again once it runs.
        if time.monotonic() - _last_used >= config.IDLE_UNLOAD_S and _on_mlx(_drop_model, only_if_idle=True):
            return


def _start_reaper():
    global _reaper
    if config.IDLE_UNLOAD_S > 0 and (_reaper is None or not _reaper.is_alive()):
        _reaper = threading.Thread(target=_reap_loop, name="imagegen-idle-unload", daemon=True)
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

    models = {
        key: {
            "repo": spec["repo"],
            "path": str(config.model_path(key)),
            # False until the first generation with it (or `imagegen-prepare --model <key>`) downloads the weights.
            "weights_ready": prepare.weights_ready(config.model_path(key)),
            "default_steps": spec["steps"],
            "img2img": spec["img2img"],
        }
        for key, spec in config.MODELS.items()
    }
    return {
        "status": "ok",
        "model": config.HF_REPO,
        "model_path": str(config.MODEL_PATH),
        # The default model (Z-Image); per-model readiness is under "models".
        "weights_ready": models[config.DEFAULT_MODEL]["weights_ready"],
        "models": models,
        "quantize": config.QUANTIZE,
        "loaded": _model is not None,
        "loaded_model": _model_key,
        "load_time_s": _load_time_s,
        "idle_unload_s": config.IDLE_UNLOAD_S,
        "device": "mlx-metal" if platform.system() == "Darwin" and platform.machine() == "arm64" else "mlx",
        "output_dir": str(config.OUTPUT_DIR),
    }


def _validate(
    prompt: str,
    width: int,
    height: int,
    steps: int,
    count: int,
    image_strength: float | None,
    model: str,
    img2img: bool,
):
    if model not in config.MODELS:
        raise ServiceError(f"model must be one of {sorted(config.MODELS)}")
    if img2img and not config.MODELS[model]["img2img"]:
        raise ServiceError(f"{model} does not support img2img; use model='zimage' for image variations")
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
    steps: int | None = None,
    seed: int | None = None,
    count: int = 1,
    image_path: str | None = None,
    image_strength: float | None = None,
    output_name: str | None = None,
    model: str = config.DEFAULT_MODEL,
) -> dict:
    """Text to image (or img2img with image_path, Z-Image only). Writes PNGs into OUTPUT_DIR and returns their paths.

    Width and height are rounded down to multiples of 16. With count > 1, seeds run seed, seed+1, ... steps defaults
    to the model's own (Z-Image 9, Boogu 8).
    """
    if model in config.MODELS and steps is None:
        steps = config.MODELS[model]["steps"]
    _validate(prompt, width, height, steps or 0, count, image_strength, model, bool(image_path))
    width, height = width // 16 * 16, height // 16 * 16
    init = _input_image(image_path) if image_path else None
    if init is not None and image_strength is None:
        image_strength = 0.4
    base_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    images = _on_mlx(
        _generate, model, prompt, width, height, steps, base_seed, count, init, image_strength, output_name
    )
    return {
        "model": model,
        "images": images,
        "width": width,
        "height": height,
        "steps": steps,
        "quantize": config.QUANTIZE,
        "load_time_s": _load_time_s,
    }


def _generate(key, prompt, width, height, steps, base_seed, count, init, image_strength, output_name) -> list[dict]:
    global _last_used
    images = []
    model = _ensure_model(key)
    # Boogu's generate_image has no img2img parameters, so they are passed only when used.
    extra = {"image_path": str(init), "image_strength": image_strength} if init else {}
    try:
        for i in range(count):
            s = base_seed + i
            t0 = time.perf_counter()
            img = model.generate_image(
                seed=s, prompt=prompt, num_inference_steps=steps, width=width, height=height, **extra
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
    return images
