"""HTTP API (FastAPI). Docs at /docs, OpenAPI at /openapi.json.

Clips take ~10+ minutes, so /generate and /img2video queue a job and return 202 at once; poll /jobs/{job_id}.
"""

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
    title="Wan Video Service",
    version="0.1.0",
    description="Local text/image-to-video with Wan 2.2 TI2V-5B (Alibaba, Apache-2.0) on Apple Silicon via mlx-gen. "
    "Generation runs as background jobs.",
    dependencies=[Depends(_auth)],
)


@app.exception_handler(core.ServiceError)
async def _service_error(_: Request, e: core.ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Subject and action, camera, lighting and style. Detailed prompts work best.")
    width: int = Field(832, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 32.")
    height: int = Field(480, ge=core.MIN_SIDE, le=core.MAX_SIDE, description="Rounded down to a multiple of 32.")
    duration_s: float = Field(5.0, ge=core.MIN_DURATION_S, le=core.MAX_DURATION_S, description="Up to ~5 s at 24 fps.")
    steps: int | None = Field(None, ge=core.MIN_STEPS, le=core.MAX_STEPS, description="Default WAN_STEPS (25).")
    seed: int | None = Field(None, description="Fix for reproducible output; random if omitted.")
    image_path: str | None = Field(None, description="Local image to use as the first frame (image-to-video).")
    negative_prompt: str | None = Field(None, description="What to avoid; Wan's default negative prompt if omitted.")
    output_name: str | None = Field(None, description="Output file stem; a unique name is generated if omitted.")


def _with_url(job: dict, request: Request) -> dict:
    if job.get("result"):
        job["result"]["url"] = f"{str(request.base_url).rstrip('/')}/files/{job['result']['name']}"
    return job


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


@app.post("/generate", status_code=202, tags=["video"])
def generate(req: GenerateRequest):
    return core.submit(**req.model_dump())


@app.post("/img2video", status_code=202, tags=["video"])
async def img2video(
    prompt: str = Form(...),
    image: UploadFile = File(..., description="First frame (png/jpg/webp)"),
    width: int = Form(832, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    height: int = Form(480, ge=core.MIN_SIDE, le=core.MAX_SIDE),
    duration_s: float = Form(5.0, ge=core.MIN_DURATION_S, le=core.MAX_DURATION_S),
    steps: int | None = Form(None, ge=core.MIN_STEPS, le=core.MAX_STEPS),
    seed: int | None = Form(None),
    negative_prompt: str | None = Form(None),
    output_name: str | None = Form(None),
):
    raw = await _read_upload(image, "Image")
    init = core.save_upload(image.filename or "", raw)
    try:
        return core.submit(
            cleanup_path=str(init),
            prompt=prompt,
            width=width,
            height=height,
            duration_s=duration_s,
            steps=steps,
            seed=seed,
            image_path=str(init),
            negative_prompt=negative_prompt,
            output_name=output_name,
        )
    except BaseException:
        init.unlink(missing_ok=True)
        raise


@app.get("/jobs", tags=["video"])
def list_jobs(request: Request):
    return [_with_url(j, request) for j in core.list_jobs()]


@app.get("/jobs/{job_id}", tags=["video"])
async def get_job(job_id: str, request: Request, wait_s: float = 0.0):
    """With ?wait_s=N, hold the request up to N seconds (max 300) until the job finishes."""
    job = await anyio.to_thread.run_sync(lambda: core.get_job(job_id, wait_s))
    return _with_url(job, request)


@app.get("/files/{name}", tags=["video"])
def get_file(name: str):
    return FileResponse(core.output_file(name), media_type="video/mp4")


def main():
    uvicorn.run("wan_service.api:app", host=config.API_HOST, port=config.API_PORT, reload=False)


if __name__ == "__main__":
    main()
