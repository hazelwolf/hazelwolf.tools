"""Environment + path configuration. Import this module before torch / huggingface_hub."""
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


# Model weights: the tool-local ./models unless AUDIOCRAFT_MODELS_DIR is set.
MODELS_DIR = _path("AUDIOCRAFT_MODELS_DIR", TOOL_ROOT / "models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(MODELS_DIR / "torch"))

OUTPUT_DIR = _path("AUDIOCRAFT_OUTPUT_DIR", TOOL_ROOT / "outputs")
UPLOAD_DIR = _path("AUDIOCRAFT_UPLOAD_DIR", TOOL_ROOT / "outputs" / "_uploads")
for _d in (OUTPUT_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DEVICE = os.environ.get("AUDIOCRAFT_DEVICE") or None  # None -> cuda if available else cpu
MAX_LOADED_MODELS = int(os.environ.get("AUDIOCRAFT_MAX_LOADED_MODELS", "1"))
MAX_DURATION = float(os.environ.get("AUDIOCRAFT_MAX_DURATION", "120"))
MAX_BATCH = int(os.environ.get("AUDIOCRAFT_MAX_BATCH", "4"))

API_HOST = os.environ.get("AUDIOCRAFT_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("AUDIOCRAFT_PORT", "8101"))
API_KEY = os.environ.get("AUDIOCRAFT_API_KEY") or None  # optional bearer token for the HTTP API
MAX_INPUT_SECONDS = float(os.environ.get("AUDIOCRAFT_MAX_INPUT_SECONDS", "300"))
