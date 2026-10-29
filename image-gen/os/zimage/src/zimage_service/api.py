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
    title="Z-Image Service",
    version="0.1.0",
    description="Local text-to-image with Z-Image-Turbo (Tongyi-MAI), running on Apple Silicon through mflux (MLX).",
    dependencies=[Depends(_auth)],
)


@app.exception_handler(core.ServiceError)
async def _service_error(_: Request, e: core.ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="What to draw. Long, descriptive prompts work best; text in quotes renders.")
    width: int = Field(1024, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 16.")
    height: int = Field(1024, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 16.")
    steps: int = Field(9, ge=1, le=50, description="Turbo is distilled for 8-9 steps.")
    seed: int | None = Field(None, description="Fix for reproducible output; random if omitted.")
    count: int = Field(1, ge=1, le=core.MAX_COUNT, description="Images to make, with seeds seed, seed+1, ...")
    image_path: str | None = Field(None, description="Local init image for img2img.")
    image_strength: float | None = Field(None, gt=0, lt=1, description="img2img: how much of the init image to keep.")
    output_name: str | None = Field(None, description="Output file stem; a unique name is generated if omitted.")


def _with_urls(res: dict, request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    for img in res["images"]:
        img["url"] = f"{base}/files/{img['name']}"
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


@app.post("/generate", tags=["images"])
async def generate(req: GenerateRequest, request: Request):
    # Generation holds the GPU for seconds; keep it off the event loop so /health stays responsive.
    res = await anyio.to_thread.run_sync(lambda: core.generate(**req.model_dump()))
    return _with_urls(res, request)


@app.post("/img2img", tags=["images"])
async def img2img(
    request: Request,
    prompt: str = Form(...),
    image: UploadFile = File(..., description="Init image (png/jpg/webp)"),
    image_strength: float = Form(0.4, gt=0, lt=1),
    width: int = Form(1024, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    height: int = Form(1024, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    steps: int = Form(9, ge=1, le=50),
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
                steps=steps,
                seed=seed,
                image_path=str(init),
                image_strength=image_strength,
                output_name=output_name,
            )
        )
    finally:
        init.unlink(missing_ok=True)
    return _with_urls(res, request)


@app.get("/files/{name}", tags=["images"])
def get_file(name: str):
    return FileResponse(core.output_file(name), media_type="image/png")


def main():
    uvicorn.run("zimage_service.api:app", host=config.API_HOST, port=config.API_PORT, reload=False)


if __name__ == "__main__":
    main()
