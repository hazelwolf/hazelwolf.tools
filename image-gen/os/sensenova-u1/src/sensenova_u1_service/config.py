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


# Model weights: the tool-local ./models unless SENSENOVA_U1_MODELS_DIR is set.
MODELS_DIR = _path("SENSENOVA_U1_MODELS_DIR", TOOL_ROOT / "models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))

OUTPUT_DIR = _path("SENSENOVA_U1_OUTPUT_DIR", TOOL_ROOT / "outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = os.environ.get("SENSENOVA_U1_MODEL", "sensenova/SenseNova-U1.5-8B-MoT")
DEVICE = os.environ.get("SENSENOVA_U1_DEVICE") or None  # None -> best available accelerator
DTYPE = os.environ.get("SENSENOVA_U1_DTYPE", "bfloat16")
# full | fast | balanced | low (upstream layer offload). `fast` keeps what fits in VRAM and streams the rest.
VRAM_MODE = os.environ.get("SENSENOVA_U1_VRAM_MODE", "fast")
VRAM_BUDGET_GIB = (
    float(os.environ["SENSENOVA_U1_VRAM_BUDGET_GIB"]) if os.environ.get("SENSENOVA_U1_VRAM_BUDGET_GIB") else None
)
GGUF_CHECKPOINT = os.environ.get("SENSENOVA_U1_GGUF") or None  # optional quantized weights for the default model
ATTN_BACKEND = os.environ.get("SENSENOVA_U1_ATTN_BACKEND", "auto")  # auto | flash | sdpa
MAX_BATCH = int(os.environ.get("SENSENOVA_U1_MAX_BATCH", "4"))

API_HOST = os.environ.get("SENSENOVA_U1_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("SENSENOVA_U1_PORT", "8130"))
MCP_PORT = int(os.environ.get("SENSENOVA_U1_MCP_PORT", "8131"))
API_KEY = os.environ.get("SENSENOVA_U1_API_KEY") or None  # optional bearer token for the HTTP API
