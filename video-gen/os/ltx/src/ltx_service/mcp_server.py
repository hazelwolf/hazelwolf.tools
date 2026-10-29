"""MCP server (stdio by default; --transport streamable-http for HTTP).

Videos move by file path, never base64, so nothing large enters the agent's context.
"""

from __future__ import annotations

import argparse

import anyio
from mcp.server.fastmcp import FastMCP

from . import config, core

mcp = FastMCP("ltx", host=config.API_HOST, port=config.MCP_PORT)


async def _run(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except core.ServiceError as e:
        raise ValueError(str(e)) from None


@mcp.tool()
async def check_health() -> dict:
    """Check the LTX video tool: whether the model is downloaded (weights_ready), whether an HF token is set, and whether the pipeline is loaded.

    If weights_ready is false, this is the first use: the gated model pack (~45 GB) must be downloaded. It needs the LTX-2.x license accepted on Hugging Face and HF_TOKEN set (hf_token_set). Run `uv run --directory <tool dir> ltx-prepare` in the background and wait for weights_ready, because generate_video would otherwise do it inside one very long call."""
    return await _run(core.health)


@mcp.tool()
async def generate_video(
    prompt: str,
    width: int = 768,
    height: int = 512,
    duration_s: float | None = 5.0,
    fps: float = 24.0,
    seed: int | None = None,
    image_path: str | None = None,
    output_name: str | None = None,
) -> dict:
    """Text-to-video (or image-to-video) with synchronized stereo audio, using LTX-2.5 locally on this Mac. Writes an MP4 to the tool's outputs/ folder and returns its absolute path.

    Args:
        prompt: One flowing paragraph: the subject and action in order, camera movement, lighting and style, and the sounds (dialogue in quotes, ambience, music). Detailed prompts work best.
        width: 256-1920, rounded down to a multiple of 64. 768x512 by default; 1280x704 for HD (slower).
        height: 256-1920, rounded down to a multiple of 64.
        duration_s: 1-20 seconds (default 5). Pass null to let the model pick a length from the prompt.
        fps: 24, 25 or 30.
        seed: Fix for reproducible output; random if omitted (the seed used is returned).
        image_path: Optional local image to animate as the first frame.
        output_name: Output file stem.

    A 5 s clip at 768x512 takes about 70 s on an M5 Max; HD and longer clips take several minutes (time grows faster than resolution x duration). Tell the user before starting. The first call also downloads the model if check_health shows weights_ready=false.
    """
    return await _run(
        core.generate,
        prompt=prompt,
        width=width,
        height=height,
        duration_s=duration_s,
        fps=fps,
        seed=seed,
        image_path=image_path,
        output_name=output_name,
    )


@mcp.tool()
async def unload_model() -> dict:
    """Free the pipeline's memory now instead of waiting for the idle timeout."""
    return await _run(core.unload)


def main():
    parser = argparse.ArgumentParser(description="LTX video MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
