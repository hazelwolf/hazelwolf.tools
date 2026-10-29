"""Environment + path configuration. Imported first by the package __init__."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

TOOL_ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_DIR = TOOL_ROOT / "upstream"


def _find_workspace_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "INSTRUCTIONS.md").exists():
            return p
    return TOOL_ROOT


WORKSPACE_ROOT = _find_workspace_root()
load_dotenv(WORKSPACE_ROOT / ".env")  # shared; real env vars still win
load_dotenv(TOOL_ROOT / ".env", override=True)  # optional tool-local overrides


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if not raw:
        return default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (WORKSPACE_ROOT / p).resolve()


def _int_or_none(raw: str | None) -> int | None:
    return int(raw) if raw and raw.strip().lower() not in ("none", "0", "bf16") else None


# Hugging Face repo and the revision this tool was tested against.
HF_REPO = os.environ.get("ZIMAGE_HF_REPO", "Tongyi-MAI/Z-Image-Turbo")
HF_REVISION = os.environ.get("ZIMAGE_HF_REVISION", "f332072aa78be7aecdf3ee76d5c247082da564a6")

MODELS_DIR = _path("ZIMAGE_MODELS_DIR", TOOL_ROOT / "models")
OUTPUT_DIR = _path("ZIMAGE_OUTPUT_DIR", TOOL_ROOT / "outputs")
for _d in (MODELS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))

# 8-bit is the default for this machine: same images as bf16 to the eye, about half the memory and faster
# load. Empty / "bf16" runs the unquantized weights. See README "Optimization".
QUANTIZE = _int_or_none(os.environ.get("ZIMAGE_QUANTIZE", "8"))
# Local mflux-saved copy at that bit width. Made on first use (or by `zimage-prepare`) if missing.
MODEL_PATH = _path(
    "ZIMAGE_MODEL_PATH", MODELS_DIR / (f"z-image-turbo-q{QUANTIZE}" if QUANTIZE else "z-image-turbo-bf16")
)
# Keep the original ~33 GB HF download after the quantized copy is saved (only needed for other bit widths).
KEEP_DOWNLOAD = os.environ.get("ZIMAGE_KEEP_DOWNLOAD", "").strip().lower() in ("1", "true", "yes")

# Free the model after this many idle seconds (0 = keep it loaded).
IDLE_UNLOAD_S = float(os.environ.get("ZIMAGE_IDLE_UNLOAD_S", "900"))
# Cap on MLX's buffer cache in GB, so freed activations go back to the system (0 = MLX default).
MLX_CACHE_LIMIT_GB = float(os.environ.get("ZIMAGE_MLX_CACHE_LIMIT_GB", "4"))

API_HOST = os.environ.get("ZIMAGE_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("ZIMAGE_PORT", "8130"))
MCP_PORT = int(os.environ.get("ZIMAGE_MCP_PORT", "8131"))
API_KEY = os.environ.get("ZIMAGE_API_KEY") or None  # optional bearer token for our HTTP API
MAX_UPLOAD_MB = int(os.environ.get("ZIMAGE_MAX_UPLOAD_MB", "50"))
