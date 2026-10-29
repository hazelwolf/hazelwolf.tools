"""Download the LTX-2.5 MLX pack from Hugging Face.

The API and MCP server call `ensure_weights()` on first use, so this runs by itself when the tool is first used.
Run it ahead of time to avoid a long first call (~45 GB):

uv run ltx-prepare            # download the distilled files of LTX_HF_REPO
uv run ltx-prepare --bench    # also time a 768x512, 5 s clip

The pack is gated: accept the LTX-2.x license on its Hugging Face page once, and put an HF_TOKEN in tools/.env
(or run `hf auth login`).
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from . import config

log = logging.getLogger("ltx")

# Files the distilled pipeline cannot run without; their presence means the pack is complete.
_REQUIRED = ("transformer-distilled.safetensors", "text_encoder.safetensors", "spatial_upscaler_x2_v1_0.safetensors")


class WeightsUnavailable(RuntimeError):
    """The gated pack could not be downloaded (no token, or license not accepted)."""


def local_pack() -> Path | None:
    """The pack directory if it is fully on disk, else None. Never touches the network."""
    if config.MODEL_PATH is not None:
        return config.MODEL_PATH if all((config.MODEL_PATH / f).exists() for f in _REQUIRED) else None
    from huggingface_hub import snapshot_download

    try:
        path = Path(
            snapshot_download(
                config.HF_REPO,
                revision=config.HF_REVISION,
                ignore_patterns=config.HF_IGNORE,
                local_files_only=True,
            )
        )
    except Exception:  # noqa: BLE001 - any cache miss means "not downloaded"
        return None
    return path if all((path / f).exists() for f in _REQUIRED) else None


def weights_ready() -> bool:
    return local_pack() is not None


def ensure_weights() -> Path:
    """Return the local pack directory, downloading it on first use.

    A file lock keeps the API and MCP processes from downloading at the same time; the second one waits and then
    finds the pack ready. Interrupted downloads resume.
    """
    from filelock import FileLock
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

    path = local_pack()
    if path is not None:
        return path
    if config.MODEL_PATH is not None:
        raise WeightsUnavailable(f"LTX_MODEL_PATH {config.MODEL_PATH} is missing files: {', '.join(_REQUIRED)}")
    with FileLock(str(config.MODELS_DIR / ".prepare.lock")):
        path = local_pack()
        if path is not None:
            return path
        log.warning("First use: downloading %s (~45 GB) into %s", config.HF_REPO, config.MODELS_DIR / "huggingface")
        t0 = time.perf_counter()
        try:
            path = Path(
                snapshot_download(config.HF_REPO, revision=config.HF_REVISION, ignore_patterns=config.HF_IGNORE)
            )
        except (GatedRepoError, RepositoryNotFoundError) as e:
            raise WeightsUnavailable(
                f"{config.HF_REPO} is gated. Accept the LTX-2.x Community License at "
                f"https://huggingface.co/{config.HF_REPO} with your Hugging Face account, then set HF_TOKEN in "
                f"tools/.env (or run `hf auth login`). ({type(e).__name__})"
            ) from None
        log.warning("Weights ready in %.0fs", time.perf_counter() - t0)
    return path


def bench(runs: int = 2) -> None:
    from . import core

    for i in range(runs):
        res = core.generate(
            "A red fox trots through fresh snow in soft winter light, its breath visible, gentle wind in the trees",
            duration_s=5,
            seed=42 + i,
            output_name="bench",
        )
        print(f"run {i + 1}: {res['generation_time_s']}s for {res['duration_s']}s of video -> {res['path']}")
    print(f"peak memory: {res['peak_memory_gb']} GB")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", action="store_true", help="Time two 768x512, 5 s clips after downloading.")
    args = parser.parse_args()
    try:
        print(f"Pack ready at {ensure_weights()}")
    except WeightsUnavailable as e:
        raise SystemExit(str(e)) from None
    if args.bench:
        bench()


if __name__ == "__main__":
    main()
