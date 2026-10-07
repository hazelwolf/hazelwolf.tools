"""Reading input audio and writing generated audio (soundfile based - no ffmpeg binary needed)."""
from __future__ import annotations

import base64
import re
import time
import uuid
from pathlib import Path

import soundfile as sf
import torch

from . import config
from .errors import ServiceError
from .schemas import AudioInput, OutputFile, OutputOptions

_SF_FORMATS = {"wav": ("WAV", "PCM_16"), "flac": ("FLAC", "PCM_16"), "ogg": ("OGG", "VORBIS"), "mp3": ("MP3", None)}
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def save_upload(data: bytes, filename: str | None) -> str:
    uid = uuid.uuid4().hex
    suffix = Path(filename or "").suffix[:8]
    (config.UPLOAD_DIR / f"{uid}{suffix}").write_bytes(data)
    return uid


def resolve_path(src: AudioInput) -> Path:
    """Return a local file for an AudioInput (base64 is spooled to the upload dir)."""
    if src.path:
        p = Path(src.path).expanduser()
        if not p.is_file():
            raise ServiceError(f"Audio file not found: {src.path}", 404)
        return p
    if src.upload_id:
        if not _ID_RE.match(src.upload_id):
            raise ServiceError("Invalid upload_id", 400)
        matches = list(config.UPLOAD_DIR.glob(f"{src.upload_id}*"))
        if not matches:
            raise ServiceError(f"Unknown upload_id {src.upload_id}", 404)
        return matches[0]
    try:
        data = base64.b64decode(src.base64 or "", validate=False)
    except Exception as e:  # noqa: BLE001
        raise ServiceError(f"Invalid base64 audio: {e}", 400) from None
    uid = save_upload(data, None)
    return next(config.UPLOAD_DIR.glob(f"{uid}*"))


def load_audio(src: AudioInput, max_seconds: float | None = None) -> tuple[torch.Tensor, int]:
    """Return ([C, T] float32 waveform, sample_rate)."""
    from audiocraft.data.audio import audio_read

    path = resolve_path(src)
    try:
        wav, sr = audio_read(path, duration=max_seconds if max_seconds else -1.0)
    except Exception as e:  # noqa: BLE001
        raise ServiceError(f"Could not decode audio ({path.name}): {e}", 400) from None
    return wav.float(), int(sr)


def save_audio(wav: torch.Tensor, sample_rate: int, stem: str, opts: OutputOptions,
               prompt: str | None = None) -> OutputFile:
    """Normalise and write a [C, T] (or [T]) waveform to OUTPUT_DIR."""
    from audiocraft.data.audio_utils import normalize_audio

    wav = wav.detach().float().cpu()
    if wav.dim() == 1:
        wav = wav[None]
    wav = normalize_audio(wav, True, opts.normalize, sample_rate=sample_rate, stem_name=stem,
                          loudness_compressor=True, log_clipping=False)
    fmt, subtype = _SF_FORMATS[opts.format]
    out = config.OUTPUT_DIR / f"{stem}.{opts.format}"
    try:
        sf.write(str(out), wav.T.numpy(), sample_rate, format=fmt, subtype=subtype)
    except Exception as e:  # noqa: BLE001
        raise ServiceError(f"Could not encode {opts.format}: {e}", 500) from None
    b64 = base64.b64encode(out.read_bytes()).decode() if opts.include_base64 else None
    return OutputFile(name=out.name, path=str(out), format=opts.format, bytes=out.stat().st_size,
                      prompt=prompt, base64=b64)


def new_stem(tag: str, idx: int = 0) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", tag.split("/")[-1])
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{safe}_{idx}_{uuid.uuid4().hex[:6]}"


