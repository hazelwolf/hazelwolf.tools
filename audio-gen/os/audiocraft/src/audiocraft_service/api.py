"""HTTP API (FastAPI). Docs at /docs, OpenAPI at /openapi.json."""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from . import (
    audio_io,
    config,
    core,
)
from .errors import ServiceError
from .schemas import (
    CodecReconstructRequest,
    ContinuationRequest,
    GenerateRequest,
    GenerationResult,
    JascoRequest,
    MbdRegenerateRequest,
    MelodyRequest,
    UnconditionalRequest,
    WatermarkDetectRequest,
    WatermarkEmbedRequest,
)


def _auth(authorization: str | None = Header(None)):
    if config.API_KEY and authorization != f"Bearer {config.API_KEY}":
        raise HTTPException(401, "Missing or invalid bearer token")


app = FastAPI(title="AudioCraft Service", version="0.1.0",
              description="Meta AudioCraft: MusicGen, MusicGen-Style, AudioGen, MAGNeT, JASCO, EnCodec, "
                          "Multi-Band Diffusion, AudioSeal.", dependencies=[Depends(_auth)])


@app.exception_handler(ServiceError)
async def _service_error(_: Request, e: ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


@app.exception_handler(Exception)
async def _unhandled(_: Request, e: Exception):
    return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


def _urls(res: GenerationResult, request: Request) -> GenerationResult:
    base = str(request.base_url).rstrip("/")
    for f in res.files:
        f.url = f"{base}/v1/files/{f.name}"
    return res


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/v1/models", tags=["meta"])
def models():
    return core.list_models()


@app.get("/v1/status", tags=["meta"])
def status():
    return core.status()


@app.post("/v1/unload", tags=["meta"], summary="Free GPU memory by unloading all models")
def unload():
    return core.unload_all()


@app.post("/v1/uploads", tags=["files"], summary="Upload an input audio/tensor file")
async def upload(file: UploadFile = File(...)):
    uid = audio_io.save_upload(await file.read(), file.filename)
    return {"upload_id": uid, "filename": file.filename}


@app.get("/v1/files", tags=["files"])
def list_files(limit: int = 50):
    files = sorted((p for p in config.OUTPUT_DIR.iterdir() if p.is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "bytes": p.stat().st_size} for p in files[:limit]]


@app.get("/v1/files/{name}", tags=["files"])
def get_file(name: str):
    p = config.OUTPUT_DIR / Path(name).name
    if not p.is_file():
        raise HTTPException(404, "No such file")
    return FileResponse(p)


@app.post("/v1/generate", tags=["generate"], response_model=GenerationResult,
          summary="Text to audio (MusicGen, AudioGen, MAGNeT, Audio-MAGNeT, JASCO text-only)")
def generate(req: GenerateRequest, request: Request):
    return _urls(core.generate(req), request)


@app.post("/v1/generate/unconditional", tags=["generate"], response_model=GenerationResult)
def generate_unconditional(req: UnconditionalRequest, request: Request):
    return _urls(core.generate_unconditional(req), request)


@app.post("/v1/generate/melody", tags=["generate"], response_model=GenerationResult,
          summary="Text + melody (MusicGen melody) or style audio (MusicGen-Style)")
def generate_melody(req: MelodyRequest, request: Request):
    return _urls(core.generate_with_melody(req), request)


@app.post("/v1/generate/continuation", tags=["generate"], response_model=GenerationResult)
def generate_continuation(req: ContinuationRequest, request: Request):
    return _urls(core.continue_audio(req), request)


@app.post("/v1/generate/jasco", tags=["generate"], response_model=GenerationResult,
          summary="Text + chords + drums (+ melody) to music with JASCO")
def generate_jasco(req: JascoRequest, request: Request):
    return _urls(core.generate_jasco(req), request)


@app.post("/v1/codec/reconstruct", tags=["codec"], response_model=GenerationResult,
          summary="EnCodec encode+decode round trip")
def codec_reconstruct(req: CodecReconstructRequest, request: Request):
    return _urls(core.codec_reconstruct(req), request)


@app.post("/v1/mbd/regenerate", tags=["codec"], response_model=GenerationResult,
          summary="Re-synthesise audio through EnCodec 24 kHz + Multi-Band Diffusion")
def mbd_regenerate(req: MbdRegenerateRequest, request: Request):
    return _urls(core.mbd_regenerate(req), request)


@app.post("/v1/watermark/embed", tags=["watermark"], response_model=GenerationResult)
def watermark_embed(req: WatermarkEmbedRequest, request: Request):
    return _urls(core.watermark_embed(req), request)


@app.post("/v1/watermark/detect", tags=["watermark"])
def watermark_detect(req: WatermarkDetectRequest):
    return core.watermark_detect(req)


def main():
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)


if __name__ == "__main__":
    main()
