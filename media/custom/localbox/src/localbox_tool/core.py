"""Resolve destination tags and write image/video files. Shared by the API and MCP server."""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import BinaryIO

from dotenv import load_dotenv

_here = Path(__file__).resolve()
_root = next(p for p in _here.parents if (p / "INSTRUCTIONS.md").exists())
load_dotenv(_root / ".env")
load_dotenv(_here.parents[2] / ".env", override=True)


def tool_root() -> Path:
    return _here.parents[2]


def workspace_root() -> Path:
    return _root


# Relative destination paths resolve against the workspace root.
DEFAULT_COMFY = "creative/os/creative-workflows/input"
DEFAULT_DESTINATIONS = f"comfy={DEFAULT_COMFY}"
DEFAULT_TAG = "comfy"

ALLOWED_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".mp4",
        ".webm",
        ".mov",
        ".mkv",
    }
)

_CHUNK = 1024 * 1024


class LocalboxError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def bind_host() -> str:
    return os.environ.get("LOCALBOX_HOST", "0.0.0.0")


def bind_port() -> int:
    raw = os.environ.get("LOCALBOX_PORT", "8120")
    try:
        port = int(raw)
    except ValueError as e:
        raise LocalboxError(f"LOCALBOX_PORT is not an integer: {raw}", status=500) from e
    if not 1 <= port <= 65535:
        raise LocalboxError(f"LOCALBOX_PORT out of range: {port}", status=500)
    return port


def max_bytes() -> int:
    raw = os.environ.get("LOCALBOX_MAX_MB", "2048")
    try:
        mb = int(raw)
    except ValueError as e:
        raise LocalboxError(f"LOCALBOX_MAX_MB is not an integer: {raw}", status=500) from e
    if mb < 1:
        raise LocalboxError(f"LOCALBOX_MAX_MB must be at least 1: {mb}", status=500)
    return mb * 1024 * 1024


def destinations() -> dict[str, Path]:
    """Parse LOCALBOX_DESTINATIONS (`tag=/abs/path,tag2=relative/to/workspace`)."""
    raw = os.environ.get("LOCALBOX_DESTINATIONS", DEFAULT_DESTINATIONS).strip()
    if not raw:
        raw = DEFAULT_DESTINATIONS
    found: dict[str, Path] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise LocalboxError(
                f"LOCALBOX_DESTINATIONS entry {item!r} must be tag=path",
                status=500,
            )
        tag, path = item.split("=", 1)
        tag = tag.strip()
        path = path.strip()
        if not tag or not path:
            raise LocalboxError(
                f"LOCALBOX_DESTINATIONS entry {item!r} must be tag=path",
                status=500,
            )
        dest = Path(path).expanduser()
        if not dest.is_absolute():
            dest = (_root / dest).resolve()
        found[tag] = dest
    if not found:
        raise LocalboxError("No destinations configured", status=500)
    return found


def default_tag() -> str:
    tags = destinations()
    if DEFAULT_TAG in tags:
        return DEFAULT_TAG
    return next(iter(tags))


def destination_rows() -> list[dict]:
    chosen = default_tag()
    return [{"tag": tag, "path": str(path), "default": tag == chosen} for tag, path in destinations().items()]


def lan_addresses() -> list[str]:
    """Non-loopback IPv4 addresses this machine can be reached on."""
    found: list[str] = []

    def add(ip: str) -> None:
        if ip and not ip.startswith("127.") and ip not in found:
            found.append(ip)

    try:
        for res in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            add(res[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            add(sock.getsockname()[0])
    except OSError:
        pass
    return found


def lan_urls() -> list[str]:
    port = bind_port()
    return [f"http://{ip}:{port}/" for ip in lan_addresses()]


def health() -> dict:
    return {
        "status": "ok",
        "host": bind_host(),
        "port": bind_port(),
        "lan_urls": lan_urls(),
        "destinations": destination_rows(),
        "max_mb": max_bytes() // (1024 * 1024),
        "allowed_suffixes": sorted(ALLOWED_SUFFIXES),
    }


def _safe_name(filename: str) -> tuple[str, str]:
    name = Path(filename or "").name.strip()
    if not name or name in {".", ".."} or "\x00" in name:
        raise LocalboxError("Missing or invalid filename")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise LocalboxError(f"Unsupported file type {suffix or '(none)'}. Allowed: {allowed}")
    return name, suffix


def _unique_path(folder: Path, filename: str) -> Path:
    original = Path(filename)
    stem = original.stem
    suffix = original.suffix
    candidate = folder / f"{stem}{suffix}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem}-{n}{suffix}"
        n += 1
    return candidate


def _resolve_folder(tag: str | None) -> tuple[str, Path]:
    chosen = (tag or "").strip() or default_tag()
    mapping = destinations()
    if chosen not in mapping:
        known = ", ".join(sorted(mapping))
        raise LocalboxError(f"Unknown destination {chosen!r}. Known: {known}")
    folder = mapping[chosen]
    folder.mkdir(parents=True, exist_ok=True)
    return chosen, folder


def _write_stream(tag: str | None, filename: str, stream: BinaryIO) -> dict:
    safe, suffix = _safe_name(filename)
    stored = Path(safe).stem + suffix
    chosen, folder = _resolve_folder(tag)
    dest = _unique_path(folder, stored)
    limit = max_bytes()
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = stream.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise LocalboxError(
                        f"File exceeds LOCALBOX_MAX_MB ({limit // (1024 * 1024)} MB)",
                        status=413,
                    )
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise LocalboxError("Empty file")
    return {"tag": chosen, "path": str(dest), "name": dest.name, "bytes": written}


def save_stream(tag: str | None, filename: str, stream: BinaryIO) -> dict:
    return _write_stream(tag, filename, stream)


def save_path(tag: str | None, source: str) -> dict:
    """Copy a file that already exists on this machine into the destination."""
    src = Path(source).expanduser()
    if not src.is_file():
        raise LocalboxError(f"Source is not a file: {source}")
    _safe_name(src.name)
    size = src.stat().st_size
    if size == 0:
        raise LocalboxError("Empty file")
    if size > max_bytes():
        raise LocalboxError(
            f"File exceeds LOCALBOX_MAX_MB ({max_bytes() // (1024 * 1024)} MB)",
            status=413,
        )
    with src.open("rb") as stream:
        return _write_stream(tag, src.name, stream)
