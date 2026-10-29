"""MCP server. stdio by default; --transport streamable-http for HTTP."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from . import core
from .errors import FlowError

mcp = FastMCP("comfyflow", host=core.bind_host(), port=core.bind_port() + 1)


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FlowError as exc:
        raise ValueError(str(exc)) from None


@mcp.tool()
def health() -> dict:
    """Check that ComfyUI is reachable and show its GPU, free VRAM and the workflow count.
    If it is down, start it with creative/os/creative-workflows/run.sh."""
    return _guard(core.health)


@mcp.tool()
def list_workflows() -> dict:
    """List runnable workflows (ComfyUI API-format JSON) with their description and exposed parameter names."""
    return {"workflows": core.list_workflows()}


@mcp.tool()
def describe_workflow(name: str) -> dict:
    """Show one workflow's parameters (name, type, default, description) and its output nodes.
    Call this before run_workflow so you pass valid parameter names."""
    return _guard(core.describe_workflow, name)


@mcp.tool()
def run_workflow(
    name: str,
    params: dict | None = None,
    wait: bool = True,
    timeout_s: float | None = None,
    randomize_seed: bool = True,
) -> dict:
    """Run a workflow on the local ComfyUI and return the output files (absolute paths).
    `params` maps exposed names (see describe_workflow) to values, e.g. {"prompt": "a red fox", "width": 1024}.
    File parameters take a local path; it is uploaded to ComfyUI for you. Seeds are randomized unless given.
    Image workflows take about 10-20 s on this GPU, video 1-3 min. For long jobs pass wait=false, then poll get_job.
    Returns status success/error/timeout, `files` (kind image/video/audio), `seeds` used, and any `error`."""
    return _guard(core.run_workflow, name, params, wait, timeout_s, randomize_seed)


@mcp.tool()
def get_job(prompt_id: str) -> dict:
    """Status of a job: queued, running, success or error (with output files once finished)."""
    return _guard(core.get_job, prompt_id)


@mcp.tool()
def cancel_job(prompt_id: str) -> dict:
    """Cancel a queued job, or interrupt it if it is the one currently running."""
    return _guard(core.cancel_job, prompt_id)


@mcp.tool()
def import_workflow(name: str, prompt_id: str | None = None, description: str = "", overwrite: bool = False) -> dict:
    """Save a workflow that was just run in the ComfyUI UI (or the run `prompt_id`) as a reusable workflow.
    Common nodes (prompt, size, sampler, loaders, primitives) get `@name` titles so they become parameters.
    Rename nodes in ComfyUI to `@something` and re-import with overwrite to expose more."""
    return _guard(core.import_workflow, name, prompt_id, description, overwrite)


def main():
    parser = argparse.ArgumentParser(description="Comfyflow MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
