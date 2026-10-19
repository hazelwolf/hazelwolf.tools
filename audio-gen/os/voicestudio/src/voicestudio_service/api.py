"""HTTP API (FastAPI). Docs at /docs, OpenAPI at /openapi.json."""

from __future__ import annotations

import anyio
import uvicorn
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import config, core


def _auth(authorization: str | None = Header(None)):
    if config.API_KEY and authorization != f"Bearer {config.API_KEY}":
        raise HTTPException(401, "Missing or invalid bearer token")


app = FastAPI(
    title="VoiceStudio Service",
    version="0.1.0",
    description="Voice cloning, TTS in 646 languages and transcription via the local VoiceStudio backend.",
    dependencies=[Depends(_auth)],
)


@app.exception_handler(core.ServiceError)
async def _service_error(_: Request, e: core.ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


class GenerateRequest(BaseModel):
    text: str = Field(..., description="Text to speak.")
    profile_id: str | None = Field(None, description="Voice profile id from GET /voices; omit for the default voice.")
    language: str = Field("Auto", description="ISO 639 code or Auto.")
    instruct: str | None = Field(None, description="Style instruction, e.g. 'whisper', 'excited', 'narrator'.")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    steps: int | None = Field(None, ge=1, le=64, description="Diffusion steps: 8 draft, 16 balanced, 32 quality.")
    seed: int | None = None
    engine: str | None = Field(None, description="Override the TTS engine selected in the backend.")
    output_name: str | None = Field(None, description="Output file stem; a unique name is generated if omitted.")


def _with_url(res: dict, request: Request) -> dict:
    res["url"] = f"{str(request.base_url).rstrip('/')}/files/{res['name']}"
    return res


async def _read_upload(upload: UploadFile, what: str) -> bytes:
    """Read an upload without allocating more than the configured limit.

    ``size`` is checked first so a known oversized part is rejected before it is
    copied into memory. The read itself is capped at the limit plus one byte,
    which is enough to tell an over-limit body from an acceptable one.
    """
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    if upload.size is not None and upload.size > limit:
        raise core.ServiceError(f"{what} exceeds {config.MAX_UPLOAD_MB} MB")
    raw = await upload.read(limit + 1)
    if len(raw) > limit:
        raise core.ServiceError(f"{what} exceeds {config.MAX_UPLOAD_MB} MB")
    return raw


@app.get("/health", tags=["meta"])
def health():
    return core.health()


@app.get("/voices", tags=["voices"])
def list_voices():
    return core.list_voices()


@app.get("/personalities", tags=["voices"])
def list_personalities():
    return core.list_personalities()


@app.post("/voices/clone", tags=["voices"])
async def clone_voice(
    name: str = Form(...),
    ref_audio: UploadFile = File(..., description="5-30 s of clean single-speaker speech"),
    ref_text: str = Form(""),
    language: str = Form("Auto"),
    instruct: str = Form(""),
):
    raw = await _read_upload(ref_audio, "Reference audio")
    # Cloning can wait on the backend or a first-use model download. Keep that off
    # the event loop so other routes, including /health, stay responsive.
    return await anyio.to_thread.run_sync(
        core.clone_voice_bytes, name, ref_audio.filename or "ref.wav", raw, ref_text, language, instruct
    )


@app.delete("/voices/{profile_id}", tags=["voices"])
def delete_voice(profile_id: str):
    return core.delete_voice(profile_id)


@app.post("/generate", tags=["speech"])
def generate(req: GenerateRequest, request: Request):
    return _with_url(core.generate(**req.model_dump()), request)


@app.post("/transcribe", tags=["speech"])
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
    mode: str | None = Form(None, description="fast (default), accurate or reference"),
):
    raw = await _read_upload(audio, "Audio")
    return await anyio.to_thread.run_sync(
        core.transcribe_bytes, audio.filename or "audio.wav", raw, language, mode
    )


@app.get("/files/{name}", tags=["speech"])
def get_file(name: str):
    return FileResponse(core.output_file(name), media_type="audio/wav")


def main():
    uvicorn.run("voicestudio_service.api:app", host=config.API_HOST, port=config.API_PORT, reload=False)


if __name__ == "__main__":
    main()
