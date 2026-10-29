"""HTTP API. Docs at /docs, OpenAPI at /openapi.json."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import core
from .errors import FlowError

app = FastAPI(
    title="Comfyflow",
    version="0.1.0",
    description="Run ComfyUI workflows by name with named parameters. Local use only.",
)


class RunRequest(BaseModel):
    params: dict = Field(default_factory=dict, description="Exposed parameter name (or node_id.input) -> value")
    wait: bool = True
    timeout_s: float | None = None
    randomize_seed: bool = True


class ImportRequest(BaseModel):
    name: str
    prompt_id: str | None = None
    description: str = ""
    overwrite: bool = False


@app.exception_handler(FlowError)
async def _flow_error(_: Request, exc: FlowError):
    return JSONResponse({"error": str(exc)}, status_code=exc.status)


@app.get("/health", tags=["meta"])
def health():
    return core.health()


@app.get("/v1/workflows", tags=["workflows"])
def list_workflows():
    return {"workflows": core.list_workflows()}


@app.get("/v1/workflows/{name}", tags=["workflows"])
def describe_workflow(name: str):
    return core.describe_workflow(name)


@app.post("/v1/workflows/{name}/run", tags=["workflows"])
def run_workflow(name: str, body: RunRequest):
    return core.run_workflow(name, body.params, body.wait, body.timeout_s, body.randomize_seed)


@app.post("/v1/workflows/import", tags=["workflows"])
def import_workflow(body: ImportRequest):
    return core.import_workflow(body.name, body.prompt_id, body.description, body.overwrite)


@app.get("/v1/jobs/{prompt_id}", tags=["jobs"])
def get_job(prompt_id: str):
    return core.get_job(prompt_id)


@app.post("/v1/jobs/{prompt_id}/cancel", tags=["jobs"])
def cancel_job(prompt_id: str):
    return core.cancel_job(prompt_id)


def main():
    uvicorn.run("comfyflow_tool.api:app", host=core.bind_host(), port=core.bind_port(), reload=False)


if __name__ == "__main__":
    main()
