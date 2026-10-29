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


# mlx-gen's 8-bit Wan 2.2 TI2V-5B package (Apache-2.0, not gated) and the revision this tool was tested against.
# 8-bit only saves download size: mlx-gen dequantizes the transformer to bf16 at load.
HF_REPO = os.environ.get("WAN_HF_REPO", "AbstractFramework/wan2.2-ti2v-5b-diffusers-8bit")
HF_REVISION = os.environ.get("WAN_HF_REVISION", "6875952a110b6bdbcfc00d72b1d89a8e02ab0fc3")
HF_IGNORE = ["validation/*"]

MODELS_DIR = _path("WAN_MODELS_DIR", TOOL_ROOT / "models")
OUTPUT_DIR = _path("WAN_OUTPUT_DIR", TOOL_ROOT / "outputs")
for _d in (MODELS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
# A local package folder instead of the HF download.
MODEL_PATH = _path("WAN_MODEL_PATH", Path()) if os.environ.get("WAN_MODEL_PATH") else None

# Denoising steps. Wan's reference is 50; 25 halves the time with little visible loss (mlx-gen's M5 Max clips).
DEFAULT_STEPS = int(os.environ.get("WAN_STEPS", "25"))
# Finished jobs kept in memory for get_job / list_jobs.
MAX_JOBS = int(os.environ.get("WAN_MAX_JOBS", "100"))

API_HOST = os.environ.get("WAN_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("WAN_PORT", "8150"))
MCP_PORT = int(os.environ.get("WAN_MCP_PORT", "8151"))
API_KEY = os.environ.get("WAN_API_KEY") or None  # optional bearer token for our HTTP API
MAX_UPLOAD_MB = int(os.environ.get("WAN_MAX_UPLOAD_MB", "50"))
