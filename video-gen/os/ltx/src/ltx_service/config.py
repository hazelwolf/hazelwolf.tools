"""Environment + path configuration. Imported first by the package __init__."""

from __future__ import annotations

import os
from collections.abc import Mapping
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


def _flag(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


# MLX model pack (gated on Hugging Face: accept the LTX-2.x license once, then set HF_TOKEN) and the revision
# this tool was tested against. q8 fits a 48 GB Mac without streaming; q4 / bf16 packs work the same way.
DEFAULT_HF_REPO = "dgrauet/ltx-2.5-mlx-q8"
PINNED_HF_REVISION = "746ca9aacb697d2c739f544d68b584214dedcc75"


def resolve_hf_revision(repo: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Revision for snapshot_download: pinned only for DEFAULT_HF_REPO unless LTX_HF_REVISION is set."""
    env = os.environ if environ is None else environ
    if "LTX_HF_REVISION" in env:
        return env["LTX_HF_REVISION"] or None
    return PINNED_HF_REVISION if repo == DEFAULT_HF_REPO else None


HF_REPO = os.environ.get("LTX_HF_REPO", DEFAULT_HF_REPO)
HF_REVISION = resolve_hf_revision(HF_REPO)
# Only the distilled pipeline runs here, so the dev transformer and the distilled LoRA (~30 GB) are skipped.
HF_IGNORE = ["transformer-dev*", "*distilled-lora*"]

MODELS_DIR = _path("LTX_MODELS_DIR", TOOL_ROOT / "models")
OUTPUT_DIR = _path("LTX_OUTPUT_DIR", TOOL_ROOT / "outputs")
for _d in (MODELS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
# A local pack directory instead of the HF download (e.g. one converted with mlx-forge).
MODEL_PATH = _path("LTX_MODEL_PATH", Path()) if os.environ.get("LTX_MODEL_PATH") else None

# Stream transformer blocks from disk instead of holding them (for Macs with < 32 GB).
LOW_RAM = _flag("LTX_LOW_RAM")
# Free the pipeline after this many idle seconds (0 = keep it).
IDLE_UNLOAD_S = float(os.environ.get("LTX_IDLE_UNLOAD_S", "600"))

API_HOST = os.environ.get("LTX_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("LTX_PORT", "8140"))
MCP_PORT = int(os.environ.get("LTX_MCP_PORT", "8141"))
API_KEY = os.environ.get("LTX_API_KEY") or None  # optional bearer token for our HTTP API
MAX_UPLOAD_MB = int(os.environ.get("LTX_MAX_UPLOAD_MB", "50"))
