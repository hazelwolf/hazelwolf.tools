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


# Upstream backend (the VoiceStudio FastAPI server our wrapper talks to).
BACKEND_HOST = os.environ.get("VOICESTUDIO_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("VOICESTUDIO_BACKEND_PORT", "3900"))
BACKEND_URL = os.environ.get("VOICESTUDIO_BACKEND_URL") or f"http://{BACKEND_HOST}:{BACKEND_PORT}"
BACKEND_API_KEY = os.environ.get("VOICESTUDIO_BACKEND_API_KEY") or None  # only for a remote backend with auth

# Upstream state: voice profiles DB, references, history. Weights go to MODELS_DIR (HF cache).
DATA_DIR = _path("VOICESTUDIO_DATA_DIR", TOOL_ROOT / "models" / "data")
MODELS_DIR = _path("VOICESTUDIO_MODELS_DIR", TOOL_ROOT / "models")
OUTPUT_DIR = _path("VOICESTUDIO_OUTPUT_DIR", TOOL_ROOT / "outputs")
for _d in (DATA_DIR, MODELS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DEVICE = os.environ.get("VOICESTUDIO_DEVICE") or None  # None -> upstream auto (cuda / mps / cpu)

# Our wrapper API and MCP HTTP transport.
API_HOST = os.environ.get("VOICESTUDIO_API_HOST") or os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("VOICESTUDIO_PORT", "8103"))
MCP_PORT = int(os.environ.get("VOICESTUDIO_MCP_PORT", "8104"))
API_KEY = os.environ.get("VOICESTUDIO_API_KEY") or None  # optional bearer token for our HTTP API

# Generation can include a first-run model download (~2.3 GB); transcription loads Whisper.
TIMEOUT_S = float(os.environ.get("VOICESTUDIO_TIMEOUT_S", "1800"))
MAX_UPLOAD_MB = int(os.environ.get("VOICESTUDIO_MAX_UPLOAD_MB", "200"))


def backend_env() -> dict[str, str]:
    """Environment for the upstream backend process."""
    env = dict(os.environ)
    env["OMNIVOICE_DATA_DIR"] = str(DATA_DIR)
    env["OMNIVOICE_PORT"] = str(BACKEND_PORT)
    env["OMNIVOICE_BIND_HOST"] = BACKEND_HOST
    env.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
    env.setdefault("OMNIVOICE_ANALYTICS_DISABLED", "1")
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    if DEVICE:
        env["OMNIVOICE_DEVICE"] = DEVICE
    # Files mode for the upstream's own MCP endpoint at /mcp/: renders land on disk, not in context.
    env.setdefault("OMNIVOICE_MCP_OUTPUT_MODE", "files")
    env.setdefault("OMNIVOICE_MCP_BASE_PATH", str(OUTPUT_DIR))
    return env
