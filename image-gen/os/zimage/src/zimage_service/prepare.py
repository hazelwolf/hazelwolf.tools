"""Download Z-Image-Turbo from Hugging Face and save a quantized MLX copy for this machine.

The API and MCP server call `ensure_weights()` on first use, so this runs by itself when the tool is first used.
Run it ahead of time to avoid a long first call:

uv run zimage-prepare                 # download + save models/z-image-turbo-q8 (ZIMAGE_QUANTIZE)
uv run zimage-prepare --quantize 4    # another bit width
uv run zimage-prepare --bench         # also time a 1024x1024, 9-step generation
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import shutil
import time
from pathlib import Path

from . import config

log = logging.getLogger("zimage")


def weights_ready(path: Path | None = None) -> bool:
    return ((path or config.MODEL_PATH) / "transformer").is_dir()


def download() -> str:
    from huggingface_hub import snapshot_download

    # Only what mflux loads; the repo also carries ~50 MB of README assets.
    return snapshot_download(
        config.HF_REPO,
        revision=config.HF_REVISION,
        allow_patterns=["*.json", "*.txt", "text_encoder/*", "tokenizer/*", "transformer/*", "vae/*", "scheduler/*"],
    )


def remove_download() -> None:
    """Delete the original HF download (~33 GB); the quantized copy does not need it."""
    hub = Path(os.environ["HF_HOME"]) / "hub" / f"models--{config.HF_REPO.replace('/', '--')}"
    shutil.rmtree(hub, ignore_errors=True)


def save_quantized(source: str, bits: int | None, path: Path) -> None:
    """Quantize and save into a temporary folder, then rename, so a crash never leaves a half copy at `path`."""
    import mlx.core as mx
    from mflux.models.common.config import ModelConfig
    from mflux.models.z_image import ZImage

    partial = path.with_name(path.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    model = ZImage(model_config=ModelConfig.z_image_turbo(), model_path=source, quantize=bits)
    model.save_model(str(partial))
    del model
    gc.collect()
    mx.clear_cache()
    shutil.rmtree(path, ignore_errors=True)
    partial.rename(path)


def ensure_weights(force: bool = False, keep_download: bool | None = None) -> Path:
    """Make sure the quantized copy at MODEL_PATH exists, downloading and quantizing it if needed.

    A file lock keeps the API and MCP processes from preparing at the same time; the second one waits and then
    finds the copy ready.
    """
    from filelock import FileLock

    path = config.MODEL_PATH
    if weights_ready(path) and not force:
        return path
    keep = config.KEEP_DOWNLOAD if keep_download is None else keep_download
    with FileLock(str(config.MODELS_DIR / ".prepare.lock")):
        if weights_ready(path) and not force:
            return path
        bits = f"q{config.QUANTIZE}" if config.QUANTIZE else "bf16"
        log.warning("First use: downloading %s (~33 GB) and saving a %s copy to %s", config.HF_REPO, bits, path)
        t0 = time.perf_counter()
        source = download()
        save_quantized(source, config.QUANTIZE, path)
        if not keep:
            remove_download()
        log.warning("Weights ready in %.0fs", time.perf_counter() - t0)
    return path


def bench(runs: int = 2) -> None:
    from . import core

    t0 = time.perf_counter()
    core._ensure_model()
    print(f"load: {time.perf_counter() - t0:.1f}s from {core._model_source}")
    import mlx.core as mx

    mx.reset_peak_memory()
    for i in range(runs):
        res = core.generate(
            "a red fox in fresh snow, soft winter light, detailed fur",
            seed=42 + i,
            output_name=f"bench-q{config.QUANTIZE or 'bf16'}",
        )
        img = res["images"][0]
        print(f"run {i + 1}: {img['generation_time_s']}s -> {img['path']}")
    print(f"peak memory: {mx.get_peak_memory() / 1024**3:.1f} GB")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--quantize",
        type=int,
        choices=[3, 4, 5, 6, 8, 0],
        default=None,
        help="Bit width to save (0 = bf16). Default: ZIMAGE_QUANTIZE.",
    )
    parser.add_argument("--bench", action="store_true", help="Time two 1024x1024 generations after preparing.")
    parser.add_argument("--force", action="store_true", help="Re-save even if the local copy exists.")
    parser.add_argument(
        "--keep-download",
        action="store_true",
        help="Keep the original ~33 GB HF download after quantizing (default: ZIMAGE_KEEP_DOWNLOAD, off).",
    )
    args = parser.parse_args()

    if args.quantize is not None:
        config.QUANTIZE = args.quantize or None
        config.MODEL_PATH = config.MODELS_DIR / (
            f"z-image-turbo-q{config.QUANTIZE}" if config.QUANTIZE else "z-image-turbo-bf16"
        )

    if weights_ready() and not args.force:
        print(f"Local copy already at {config.MODEL_PATH}")
    else:
        ensure_weights(force=args.force, keep_download=args.keep_download or None)
    if args.bench:
        bench()


if __name__ == "__main__":
    main()
