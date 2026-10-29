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
    title="LTX Video Service",
    version="0.1.0",
    description="Local text/image-to-video with audio using LTX-2.5 (Lightricks) on Apple Silicon via ltx-2-mlx.",
    dependencies=[Depends(_auth)],
)


@app.exception_handler(core.ServiceError)
async def _service_error(_: Request, e: core.ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Scene, action, camera and sound. Detailed prompts work best.")
    width: int = Field(768, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 64.")
    height: int = Field(512, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 64.")
    duration_s: float | None = Field(
        5.0,
        ge=core.MIN_DURATION_S,
        le=core.MAX_DURATION_S,
        description="Clip length in seconds; null lets the model choose from the prompt.",
    )
    fps: float = Field(24.0, description="24, 25 or 30.")
    seed: int | None = Field(None, description="Fix for reproducible output; random if omitted.")
    image_path: str | None = Field(None, description="Local image to use as the first frame (image-to-video).")
    output_name: str | None = Field(None, description="Output file stem; a unique name is generated if omitted.")


def _with_url(res: dict, request: Request) -> dict:
    res["url"] = f"{str(request.base_url).rstrip('/')}/files/{res['name']}"
    return res


async def _read_upload(upload: UploadFile, what: str) -> bytes:
    """Read an upload, rejecting anything over the configured limit before it is fully in memory."""
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


@app.post("/unload", tags=["meta"])
def unload():
    return core.unload()


@app.post("/generate", tags=["video"])
async def generate(req: GenerateRequest, request: Request):
    # A clip takes minutes on the GPU; keep it off the event loop so /health stays responsive.
    res = await anyio.to_thread.run_sync(lambda: core.generate(**req.model_dump()))
    return _with_url(res, request)


@app.post("/img2video", tags=["video"])
async def img2video(
    request: Request,
    prompt: str = Form(...),
    image: UploadFile = File(..., description="First frame (png/jpg/webp)"),
    width: int = Form(768, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    height: int = Form(512, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    duration_s: float = Form(5.0, ge=core.MIN_DURATION_S, le=core.MAX_DURATION_S),
    fps: float = Form(24.0),
    seed: int | None = Form(None),
    output_name: str | None = Form(None),
):
    raw = await _read_upload(image, "Image")
    init = core.save_upload(image.filename or "", raw)
    try:
        res = await anyio.to_thread.run_sync(
            lambda: core.generate(
                prompt=prompt,
                width=width,
                height=height,
                duration_s=duration_s,
                fps=fps,
                seed=seed,
                image_path=str(init),
                output_name=output_name,
            )
        )
    finally:
        init.unlink(missing_ok=True)
    return _with_url(res, request)


@app.get("/files/{name}", tags=["video"])
def get_file(name: str):
    return FileResponse(core.output_file(name), media_type="video/mp4")


def main():
    uvicorn.run("ltx_service.api:app", host=config.API_HOST, port=config.API_PORT, reload=False)


if __name__ == "__main__":
    main()
