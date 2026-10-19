"""Thin client over the upstream VoiceStudio backend. Shared by the API and MCP server."""

from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

import httpx

from . import config

_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm", ".aac", ".opus"}


class ServiceError(Exception):
    """Error with an HTTP-ish status code, surfaced by both the API and MCP layers."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _client(timeout: float = 30) -> httpx.Client:
    headers = {}
    if config.BACKEND_API_KEY:
        headers["Authorization"] = f"Bearer {config.BACKEND_API_KEY}"
    return httpx.Client(base_url=config.BACKEND_URL, timeout=timeout, headers=headers)


def _detail(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        return r.text or f"HTTP {r.status_code}"
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("error") or body)
    return str(body)


def _request(method: str, path: str, *, timeout: float = 30, **kwargs) -> httpx.Response:
    try:
        with _client(timeout) as c:
            r = c.request(method, path, **kwargs)
    except httpx.ConnectError:
        raise ServiceError(
            f"VoiceStudio backend is not reachable at {config.BACKEND_URL}. Start it with "
            f"`uv run --directory {config.TOOL_ROOT} voicestudio-backend`.",
            status=503,
        ) from None
    except httpx.TimeoutException:
        raise ServiceError(f"VoiceStudio backend timed out after {timeout:.0f}s on {path}", status=504) from None
    if r.status_code == 503:
        raise ServiceError(f"VoiceStudio backend is still starting: {_detail(r)}", status=503)
    if r.status_code >= 400:
        raise ServiceError(_detail(r), status=r.status_code)
    return r


def _read_audio(path: str) -> tuple[str, bytes]:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.is_file():
        raise ServiceError(f"Audio file not found: {p}", status=404)
    if p.suffix.lower() not in _AUDIO_SUFFIXES:
        raise ServiceError(f"Unsupported audio type {p.suffix!r}; use one of {sorted(_AUDIO_SUFFIXES)}")
    if p.stat().st_size > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ServiceError(f"Audio file exceeds {config.MAX_UPLOAD_MB} MB")
    return p.name, p.read_bytes()


def _write_output(name: str | None, content: bytes) -> Path:
    """Write audio to a new file under OUTPUT_DIR.

    The free name is reserved with O_CREAT|O_EXCL, then written. Checking
    existence and writing later lets two API or MCP processes pick the same
    path and overwrite each other. An existing name is retried as -2, -3, ...
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-.")[:80]
    stem = stem or f"speech-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    base = Path(stem).stem or f"speech-{uuid.uuid4().hex[:6]}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    suffix = 0
    for _ in range(10_000):
        filename = f"{base}.wav" if suffix == 0 else f"{base}-{suffix}.wav"
        out = config.OUTPUT_DIR / filename
        try:
            fd = os.open(out, flags, 0o644)
        except FileExistsError:
            suffix = 2 if suffix == 0 else suffix + 1
            continue
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(content)
        except Exception:
            out.unlink(missing_ok=True)
            raise
        return out
    raise ServiceError("could not allocate a unique output filename", status=500)


def _num(raw: str | None):
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def output_file(name: str) -> Path:
    p = (config.OUTPUT_DIR / name).resolve()
    if p.parent != config.OUTPUT_DIR.resolve() or not p.is_file():
        raise ServiceError(f"Output not found: {name}", status=404)
    return p


# ---------------------------------------------------------------- operations


def health() -> dict:
    """Wrapper status plus the upstream backend's own /health (device, version, readiness)."""
    out = {"status": "ok", "backend_url": config.BACKEND_URL, "output_dir": str(config.OUTPUT_DIR)}
    try:
        with _client(5) as c:
            r = c.get("/health")
        out["backend"] = r.json()
        out["backend_ready"] = r.status_code == 200
    except (httpx.HTTPError, ValueError) as exc:
        out["backend"] = {"error": f"unreachable: {type(exc).__name__}"}
        out["backend_ready"] = False
    return out


def list_voices() -> list[dict]:
    profiles = _request("GET", "/profiles").json()
    keep = ("id", "name", "kind", "language", "personality", "instruct", "created_at")
    return [{k: p.get(k) for k in keep if k in p} for p in profiles]


def list_personalities():
    return _request("GET", "/personalities").json()


def generate(
    text: str,
    profile_id: str | None = None,
    language: str = "Auto",
    instruct: str | None = None,
    speed: float = 1.0,
    steps: int | None = None,
    seed: int | None = None,
    engine: str | None = None,
    ref_audio_path: str | None = None,
    ref_text: str | None = None,
    output_name: str | None = None,
) -> dict:
    """Synthesize speech and write a WAV into OUTPUT_DIR."""
    if not text.strip():
        raise ServiceError("text is empty")
    if not 0.5 <= speed <= 2.0:
        raise ServiceError("speed must be between 0.5 and 2.0")
    form: dict[str, str] = {"text": text, "language": language, "speed": str(speed)}
    for key, val in (
        ("profile_id", profile_id),
        ("instruct", instruct),
        ("num_step", steps),
        ("seed", seed),
        ("engine", engine),
        ("ref_text", ref_text),
    ):
        if val not in (None, ""):
            form[key] = str(val)
    files = None
    if ref_audio_path:
        fname, raw = _read_audio(ref_audio_path)
        files = {"ref_audio": (fname, raw, "application/octet-stream")}
    r = _request("POST", "/generate", data=form, files=files, timeout=config.TIMEOUT_S)
    out = _write_output(output_name, r.content)
    return {
        "path": str(out),
        "name": out.name,
        "bytes": len(r.content),
        "audio_id": r.headers.get("X-Audio-Id"),
        "duration_s": _num(r.headers.get("X-Audio-Duration")),
        "generation_time_s": _num(r.headers.get("X-Gen-Time")),
    }


def clone_voice(
    name: str,
    ref_audio_path: str,
    ref_text: str = "",
    language: str = "Auto",
    instruct: str = "",
) -> dict:
    """Create a voice profile from 5-30 s of clean single-speaker reference audio."""
    if not name.strip():
        raise ServiceError("name is empty")
    fname, raw = _read_audio(ref_audio_path)
    return clone_voice_bytes(name, fname, raw, ref_text=ref_text, language=language, instruct=instruct)


def clone_voice_bytes(
    name: str, filename: str, raw: bytes, ref_text: str = "", language: str = "Auto", instruct: str = ""
) -> dict:
    form = {"name": name, "kind": "clone", "ref_text": ref_text, "language": language, "instruct": instruct}
    files = {"ref_audio": (filename or "ref.wav", raw, "application/octet-stream")}
    p = _request("POST", "/profiles", data=form, files=files, timeout=config.TIMEOUT_S).json()
    return {"profile_id": p.get("id"), "name": p.get("name"), "kind": p.get("kind")}


def delete_voice(profile_id: str) -> dict:
    _request("DELETE", f"/profiles/{profile_id}")
    return {"deleted": profile_id}


def transcribe(audio_path: str, language: str | None = None, mode: str | None = None) -> dict:
    fname, raw = _read_audio(audio_path)
    return transcribe_bytes(fname, raw, language=language, mode=mode)


def transcribe_bytes(filename: str, raw: bytes, language: str | None = None, mode: str | None = None) -> dict:
    if mode not in (None, "", "fast", "accurate", "reference"):
        raise ServiceError("mode must be fast, accurate or reference")
    form = {k: v for k, v in (("language", language), ("mode", mode)) if v}
    files = {"audio": (filename or "audio.wav", raw, "application/octet-stream")}
    return _request("POST", "/transcribe", data=form, files=files, timeout=config.TIMEOUT_S).json()
