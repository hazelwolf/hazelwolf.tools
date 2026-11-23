"""Download each model from Hugging Face (pinned revision) and save a quantized MLX copy under models/."""

from __future__ import annotations

import gc
import logging
import shutil
import time
from pathlib import Path

from . import config
from .models import ModelSpec, weights_ready

log = logging.getLogger("imgeval")

# Sample images, model cards and demo media in the repos; mflux never reads them.
_IGNORE = ["assets/*", "*.md", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4"]


def download_dir(spec: ModelSpec) -> Path:
    return config.MODELS_DIR / ".download" / spec.key


def download(spec: ModelSpec) -> str:
    from huggingface_hub import snapshot_download

    # A plain folder per model instead of the HF cache: the cache keeps files in a shared hub/blobs/ store, so
    # deleting one model's cache folder would not free its space.
    return snapshot_download(
        spec.repo, revision=spec.revision, ignore_patterns=_IGNORE, local_dir=str(download_dir(spec))
    )


def remove_download(spec: ModelSpec) -> None:
    shutil.rmtree(download_dir(spec), ignore_errors=True)


def save_quantized(spec: ModelSpec, source: str, bits: int | None, path: Path) -> None:
    """Quantize and save into a temporary folder, then rename, so a crash never leaves a half copy at `path`."""
    import mlx.core as mx

    partial = path.with_name(path.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    model = spec.model_class()(quantize=bits, model_path=source, model_config=spec.model_config())
    model.save_model(str(partial))
    del model
    gc.collect()
    mx.clear_cache()
    shutil.rmtree(path, ignore_errors=True)
    partial.rename(path)


def ensure_weights(spec: ModelSpec, keep_download: bool | None = None) -> Path:
    from filelock import FileLock

    path = spec.weight_path()
    if weights_ready(path):
        return path
    path = spec.local_path()
    keep = config.KEEP_DOWNLOAD if keep_download is None else keep_download
    with FileLock(str(config.MODELS_DIR / f".{spec.key}.lock")):
        if weights_ready(path):
            return path
        log.warning("%s: downloading %s (~%.0f GB) and saving %s", spec.key, spec.repo, spec.download_gb, path.name)
        t0 = time.perf_counter()
        source = download(spec)
        save_quantized(spec, source, config.QUANTIZE, path)
        if not keep:
            remove_download(spec)
        log.warning("%s: ready in %.0fs", spec.key, time.perf_counter() - t0)
    return path
