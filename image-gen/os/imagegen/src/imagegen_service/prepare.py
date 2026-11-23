"""Download a model from Hugging Face and save a quantized MLX copy for this machine.

The API and MCP server call `ensure_weights()` on first use of each model, so this runs by itself when the tool is
first used. Run it ahead of time to avoid a long first call:

uv run imagegen-prepare                 # Z-Image-Turbo: download + save models/z-image-turbo-q8 (IMAGEGEN_QUANTIZE)
uv run imagegen-prepare --model boogu   # Boogu Image Turbo, for text-heavy images: models/boogu-q8
uv run imagegen-prepare --model all     # both
uv run imagegen-prepare --quantize 4    # another bit width
uv run imagegen-prepare --bench         # also time two 1024x1024 generations
"""

from __future__ import annotations

import argparse
import gc
import importlib
import logging
import shutil
import time
from pathlib import Path

from . import config

log = logging.getLogger("imagegen")

# Sample images and model cards in the repos; mflux never reads them.
_IGNORE = ["assets/*", "*.md", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4"]


def weights_ready(path: Path | None = None) -> bool:
    return ((path or config.MODEL_PATH) / "transformer").is_dir()


def download_dir(model: str = config.DEFAULT_MODEL) -> Path:
    return config.MODELS_DIR / ".download" / model


def download(model: str = config.DEFAULT_MODEL) -> str:
    from huggingface_hub import snapshot_download

    spec = config.MODELS[model]
    # A plain folder per model instead of the HF cache: huggingface_hub 1.x keeps cached files in a shared
    # hub/blobs/ store, so deleting one model's cache folder would not free its space.
    return snapshot_download(
        spec["repo"], revision=spec["revision"], ignore_patterns=_IGNORE, local_dir=str(download_dir(model))
    )


def remove_download(model: str = config.DEFAULT_MODEL) -> None:
    """Delete the original download; the quantized copy does not need it."""
    shutil.rmtree(download_dir(model), ignore_errors=True)


def model_class(model: str):
    from mflux.models.common.config import ModelConfig

    spec = config.MODELS[model]
    cls = getattr(importlib.import_module(spec["module"]), spec["cls"])
    return cls, getattr(ModelConfig, spec["config_fn"])()


def save_quantized(source: str, bits: int | None, path: Path, model: str = config.DEFAULT_MODEL) -> None:
    """Quantize and save into a temporary folder, then rename, so a crash never leaves a half copy at `path`."""
    import mlx.core as mx

    partial = path.with_name(path.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    cls, model_config = model_class(model)
    m = cls(model_config=model_config, model_path=source, quantize=bits)
    m.save_model(str(partial))
    del m
    gc.collect()
    mx.clear_cache()
    shutil.rmtree(path, ignore_errors=True)
    partial.rename(path)


def ensure_weights(force: bool = False, keep_download: bool | None = None, model: str = config.DEFAULT_MODEL) -> Path:
    """Make sure the model's quantized copy exists, downloading and quantizing it if needed.

    A file lock keeps the API and MCP processes from preparing at the same time; the second one waits and then
    finds the copy ready.
    """
    from filelock import FileLock

    path = config.model_path(model)
    if weights_ready(path) and not force:
        return path
    keep = config.KEEP_DOWNLOAD if keep_download is None else keep_download
    spec = config.MODELS[model]
    with FileLock(str(config.MODELS_DIR / f".prepare-{model}.lock")):
        if weights_ready(path) and not force:
            return path
        bits = f"q{config.QUANTIZE}" if config.QUANTIZE else "bf16"
        log.warning(
            "First use: downloading %s (~%d GB) and saving a %s copy to %s",
            spec["repo"],
            spec["download_gb"],
            bits,
            path,
        )
        t0 = time.perf_counter()
        source = download(model)
        save_quantized(source, config.QUANTIZE, path, model)
        if not keep:
            remove_download(model)
        log.warning("Weights ready in %.0fs", time.perf_counter() - t0)
    return path


def bench(model: str, runs: int = 2) -> None:
    import mlx.core as mx

    from . import core

    mx.reset_peak_memory()
    for i in range(runs):
        res = core.generate(
            "a red fox in fresh snow, soft winter light, detailed fur",
            seed=42 + i,
            model=model,
            output_name=f"bench-{model}-q{config.QUANTIZE or 'bf16'}",
        )
        img = res["images"][0]
        print(f"{model} run {i + 1}: {img['generation_time_s']}s -> {img['path']}")
    print(f"{model} peak memory: {mx.get_peak_memory() / 1024**3:.1f} GB")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--model",
        choices=[*config.MODELS, "all"],
        default=config.DEFAULT_MODEL,
        help="Which model to prepare (default: zimage).",
    )
    parser.add_argument(
        "--quantize",
        type=int,
        choices=[3, 4, 5, 6, 8, 0],
        default=None,
        help="Bit width to save (0 = bf16). Default: IMAGEGEN_QUANTIZE.",
    )
    parser.add_argument("--bench", action="store_true", help="Time two 1024x1024 generations after preparing.")
    parser.add_argument("--force", action="store_true", help="Re-save even if the local copy exists.")
    parser.add_argument(
        "--keep-download",
        action="store_true",
        help="Keep the original HF download after quantizing (default: IMAGEGEN_KEEP_DOWNLOAD, off).",
    )
    args = parser.parse_args()

    if args.quantize is not None:
        config.QUANTIZE = args.quantize or None
        tag = f"q{config.QUANTIZE}" if config.QUANTIZE else "bf16"
        config.MODEL_PATH = config.MODELS_DIR / f"z-image-turbo-{tag}"
        config.BOOGU_MODEL_PATH = config.MODELS_DIR / f"boogu-{tag}"

    for model in config.MODELS if args.model == "all" else [args.model]:
        path = config.model_path(model)
        if weights_ready(path) and not args.force:
            print(f"Local copy already at {path}")
        else:
            ensure_weights(force=args.force, keep_download=args.keep_download or None, model=model)
        if args.bench:
            bench(model)


if __name__ == "__main__":
    main()
