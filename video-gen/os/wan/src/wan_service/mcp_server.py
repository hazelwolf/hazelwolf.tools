"""MCP server (stdio by default; --transport streamable-http for HTTP).

Clips run as background jobs inside this process: generate_video returns a job id at once, get_video_job reports
progress and the result. Videos move by file path, never base64.
"""

from __future__ import annotations

import argparse

import anyio
from mcp.server.fastmcp import FastMCP

from . import config, core

mcp = FastMCP("wan", host=config.API_HOST, port=config.MCP_PORT)


async def _run(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except core.ServiceError as e:
        raise ValueError(str(e)) from None


@mcp.tool()
async def check_health() -> dict:
    """Check the Wan video tool: whether the model is downloaded (weights_ready), how many jobs are queued or running, and the size limit.

    If weights_ready is false, the first job also downloads the model (~18 GB, not gated). Running `uv run --directory <tool dir> wan-prepare` in the background first avoids that wait inside a job."""
    return await _run(core.health)


@mcp.tool()
async def generate_video(
    prompt: str,
    width: int = 832,
    height: int = 480,
    duration_s: float = 5.0,
    steps: int | None = None,
    seed: int | None = None,
    image_path: str | None = None,
    negative_prompt: str | None = None,
    output_name: str | None = None,
) -> dict:
    """Queue a text-to-video (or image-to-video) clip with Wan 2.2 TI2V-5B, locally on this Mac. Returns a job at once ({job_id, status, queue_position}); call get_video_job to follow it and get the MP4 path.

    Slow: about 12 minutes for 5 s at 832x480 on an M5 Max (longer at 1024x576). Tell the user before queuing. Video only, no audio (use the ltx tool when sound matters or speed matters).

    Args:
        prompt: Subject and action, camera movement, lighting and style, in plain sentences. Detailed prompts work best.
        width: 256-1024, rounded down to a multiple of 32. 832x480 by default. width x height must stay at or under 1024x576 (this Mac's memory limit; the model's native 1280x704 does not fit), e.g. 1024x576, 576x1024, 768x768.
        height: 256-1024, rounded down to a multiple of 32.
        duration_s: 0.5-5.04 seconds at 24 fps (121 frames is the model's maximum).
        steps: Denoising steps, 4-50 (default 25; 50 is Wan's reference quality, about 2x slower).
        seed: Fix for reproducible output; random if omitted (the seed used is in the result).
        image_path: Optional local image to animate as the first frame; the output follows its aspect ratio.
        negative_prompt: What to avoid; Wan's own default negative prompt is used if omitted.
        output_name: Output file stem.
    """
    return await _run(
        core.submit,
        prompt=prompt,
        width=width,
        height=height,
        duration_s=duration_s,
        steps=steps,
        seed=seed,
        image_path=image_path,
        negative_prompt=negative_prompt,
        output_name=output_name,
    )


@mcp.tool()
async def get_video_job(job_id: str, wait_s: float = 45) -> dict:
    """Status of a video job: status (queued/running/done/failed), phase and step/total_steps while running, result (path, size, duration, timing) when done, error when failed.

    Waits up to wait_s seconds (max 300, default 45) for the job to finish before answering, so one call per minute is enough to follow a job."""
    return await _run(core.get_job, job_id, wait_s)


@mcp.tool()
async def list_video_jobs() -> list[dict]:
    """All jobs in this server process, newest first. Jobs are kept in memory and cleared when the server restarts; finished MP4s stay in outputs/."""
    return await _run(core.list_jobs)


def main():
    parser = argparse.ArgumentParser(description="Wan video MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
