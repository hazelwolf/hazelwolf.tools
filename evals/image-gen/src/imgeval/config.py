"""Environment + path configuration. Imported first by the package __init__."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

EVAL_ROOT = Path(__file__).resolve().parents[2]


def _find_workspace_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "INSTRUCTIONS.md").exists():
            return p
    return EVAL_ROOT


WORKSPACE_ROOT = _find_workspace_root()
load_dotenv(WORKSPACE_ROOT / ".env")  # shared; real env vars still win
load_dotenv(EVAL_ROOT / ".env", override=True)  # optional local overrides


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if not raw:
        return default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (WORKSPACE_ROOT / p).resolve()


MODELS_DIR = _path("IMGEVAL_MODELS_DIR", EVAL_ROOT / "models")
OUTPUT_DIR = _path("IMGEVAL_OUTPUT_DIR", EVAL_ROOT / "outputs")
for _d in (MODELS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))

PROMPTS_FILE = _path("IMGEVAL_PROMPTS", EVAL_ROOT / "prompts.toml")

# Every model runs at the same bit width so the comparison is fair. 8-bit matches what imagegen serves.
_q = os.environ.get("IMGEVAL_QUANTIZE", "8").strip().lower()
QUANTIZE = None if _q in ("", "0", "none", "bf16") else int(_q)
# Keep the original HF downloads after the quantized copies are saved (tens of GB each).
KEEP_DOWNLOAD = os.environ.get("IMGEVAL_KEEP_DOWNLOAD", "").strip().lower() in ("1", "true", "yes")
# Cap on MLX's buffer cache in GB, so freed activations go back to the system (0 = MLX default).
MLX_CACHE_LIMIT_GB = float(os.environ.get("IMGEVAL_MLX_CACHE_LIMIT_GB", "4"))

# The imagegen tool's quantized copies, reused instead of a second ~33 GB download.
IMAGEGEN_MODELS_DIR = _path("IMAGEGEN_MODELS_DIR", WORKSPACE_ROOT / "image-gen" / "os" / "imagegen" / "models")
