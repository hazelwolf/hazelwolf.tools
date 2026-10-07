"""HTTP API and the single drop page. Docs at /docs, OpenAPI at /openapi.json."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from . import core

_STATIC = core.tool_root() / "static" / "index.html"

app = FastAPI(
    title="Localbox",
    version="0.1.0",
    description="Drop images and videos onto this machine. The default destination tag `comfy` "
    "writes into the ComfyUI input folder.",
)


@app.exception_handler(core.LocalboxError)
async def _localbox_error(_: Request, exc: core.LocalboxError):
    return JSONResponse({"error": str(exc)}, status_code=exc.status)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(_STATIC)


@app.get("/health", tags=["meta"])
def health():
    return core.health()


@app.get("/destinations", tags=["meta"])
def list_destinations():
    return {"default": core.default_tag(), "destinations": core.destination_rows()}


@app.post("/upload", tags=["upload"])
def upload(
    destination: str = Form("comfy"),
    file: UploadFile = File(...),
):
    return core.save_stream(destination, file.filename or "", file.file)


def main():
    uvicorn.run(
        "localbox_tool.api:app",
        host=core.bind_host(),
        port=core.bind_port(),
        reload=False,
    )


if __name__ == "__main__":
    main()
