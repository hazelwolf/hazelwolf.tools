"""Download the Wan 2.2 TI2V-5B MLX package from Hugging Face.

The API and MCP server call `ensure_weights()` on first use, so this runs by itself when the tool is first used.
Run it ahead of time to avoid a long first job (~18 GB, not gated):

uv run wan-prepare            # download WAN_HF_REPO
uv run wan-prepare --bench    # also time an 832x480, 5 s clip (about 10+ minutes)
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from . import config

log = logging.getLogger("wan")

# Index files for sharded components; VAE may be single-file or indexed (mlx-gen layout).
_INDEX_PATHS = (
    "transformer/model.safetensors.index.json",
    "text_encoder/model.safetensors.index.json",
)
_VAE_DIR = "vae"


def _shard_files(index_path: Path) -> list[Path]:
    with index_path.open(encoding="utf-8") as handle:
        weight_map = json.load(handle).get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        return []
    root = index_path.parent
    return [
        root / name for name in sorted(set(weight_map.values())) if isinstance(name, str) and not name.startswith("._")
    ]


def _vae_weight_files(vae_dir: Path) -> list[Path]:
    index = vae_dir / "model.safetensors.index.json"
    if index.is_file():
        return _shard_files(index)
    return sorted(p for p in vae_dir.glob("*.safetensors") if not p.name.startswith("._"))


def _safetensors_usable(path: Path, *, min_bytes: int = 64) -> bool:
    """True when the file exists, is non-trivially sized, and parses as safetensors with tensors."""
    if not path.is_file() or path.stat().st_size < min_bytes:
        return False
    try:
        from safetensors import safe_open

        with safe_open(str(path), framework="numpy") as handle:
            return len(handle.keys()) > 0
    except Exception:  # noqa: BLE001 - corrupt or truncated downloads fail readiness
        return False


def _complete(path: Path) -> bool:
    if not path.is_dir():
        return False
    for rel in _INDEX_PATHS:
        index = path / rel
        if not index.is_file():
            return False
        for shard in _shard_files(index):
            if not _safetensors_usable(shard):
                return False
    vae_dir = path / _VAE_DIR
    if not vae_dir.is_dir():
        return False
    vae_files = _vae_weight_files(vae_dir)
    if not vae_files:
        return False
    return all(_safetensors_usable(p) for p in vae_files)


def local_pack() -> Path | None:
    """The package directory if it is fully on disk, else None. Never touches the network."""
    if config.MODEL_PATH is not None:
        return config.MODEL_PATH if _complete(config.MODEL_PATH) else None
    from huggingface_hub import snapshot_download

    try:
        path = Path(
            snapshot_download(
                config.HF_REPO, revision=config.HF_REVISION, ignore_patterns=config.HF_IGNORE, local_files_only=True
            )
        )
    except Exception:  # noqa: BLE001 - any cache miss means "not downloaded"
        return None
    return path if _complete(path) else None


def weights_ready() -> bool:
    return local_pack() is not None


def ensure_weights() -> Path:
    """Return the local package directory, downloading it on first use.

    A file lock keeps the API and MCP processes from downloading at the same time. Interrupted downloads resume.
    """
    from filelock import FileLock
    from huggingface_hub import snapshot_download

    path = local_pack()
    if path is not None:
        return path
    if config.MODEL_PATH is not None:
        raise FileNotFoundError(
            f"WAN_MODEL_PATH {config.MODEL_PATH} is incomplete: need index shards and VAE weights under {_VAE_DIR!r}"
        )
    with FileLock(str(config.MODELS_DIR / ".prepare.lock")):
        path = local_pack()
        if path is not None:
            return path
        log.warning("First use: downloading %s (~18 GB) into %s", config.HF_REPO, config.MODELS_DIR / "huggingface")
        t0 = time.perf_counter()
        path = Path(snapshot_download(config.HF_REPO, revision=config.HF_REVISION, ignore_patterns=config.HF_IGNORE))
        log.warning("Weights ready in %.0fs", time.perf_counter() - t0)
    if not _complete(path):
        raise FileNotFoundError(f"Downloaded package at {path} is incomplete; re-run wan-prepare")
    return path


def bench() -> None:
    from . import core

    res = core.generate(
        "A red fox trots through fresh snow in soft winter light, its breath visible, gentle wind in the trees",
        duration_s=5,
        seed=42,
        output_name="bench",
        on_progress=lambda p: (
            print(f"  {p['phase']} step {p['step']}/{p['total_steps']}", flush=True)
            if p["phase"] == "denoise" and p["step"] % 5 == 0
            else None
        ),
    )
    print(
        f"{res['width']}x{res['height']}, {res['frames']} frames, {res['steps']} steps: "
        f"{res['generation_time_s']}s (load {res['load_time_s']}s), peak {res['peak_memory_gb']} GB -> {res['path']}"
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", action="store_true", help="Time an 832x480, 5 s clip after downloading.")
    args = parser.parse_args()
    print(f"Package ready at {ensure_weights()}")
    if args.bench:
        bench()


if __name__ == "__main__":
    main()
