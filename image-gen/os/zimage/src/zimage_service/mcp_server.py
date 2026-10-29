"""MCP server (stdio by default; --transport streamable-http for HTTP).

Images move by file path, never base64, so nothing large enters the agent's context.
"""

from __future__ import annotations

import argparse

import anyio
from mcp.server.fastmcp import FastMCP

from . import config, core

mcp = FastMCP("zimage", host=config.API_HOST, port=config.MCP_PORT)


async def _run(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except core.ServiceError as e:
        raise ValueError(str(e)) from None


@mcp.tool()
async def check_health() -> dict:
    """Check the Z-Image tool: whether the weights are downloaded (weights_ready), whether the model is loaded, its quantization and where outputs go.

    If weights_ready is false, this is the first use: the model must be downloaded (~33 GB) and quantized. Run `uv run --directory <tool dir> zimage-prepare` in the background and wait for weights_ready, because generate_image would otherwise do it inside one long call."""
    return await _run(core.health)


@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 9,
    seed: int | None = None,
    count: int = 1,
    image_path: str | None = None,
    image_strength: float | None = None,
    output_name: str | None = None,
) -> dict:
    """Text to image with Z-Image-Turbo, locally on this Mac. Writes PNGs to the tool's outputs/ folder and returns their absolute paths.

    Args:
        prompt: What to draw. Detailed prompts (subject, setting, lighting, style, camera) work best. Z-Image renders English and Chinese text well; put the exact words in quotes.
        width: 256-2048, rounded down to a multiple of 16. 1024x1024 by default; e.g. 1344x768 landscape, 768x1344 portrait.
        height: 256-2048, rounded down to a multiple of 16.
        steps: Denoising steps. Turbo is distilled for 9; fewer is faster and softer.
        seed: Fix for reproducible output; random if omitted (the seed used is returned).
        count: 1-8 images, seeds seed, seed+1, ...
        image_path: Optional local init image for img2img variations. It keeps the layout but does not do strong style transfer.
        image_strength: img2img only, 0-1: how much of the init image to keep (default 0.4; 0.2 changes more).
        output_name: Output file stem.

    A 1024x1024 image takes about 16 s on an M5 Max; the first call also loads the model (about 5 s). On first use (check_health weights_ready=false) this call first downloads and quantizes the weights, which can take 30+ minutes.
    """
    return await _run(
        core.generate,
        prompt=prompt,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        count=count,
        image_path=image_path,
        image_strength=image_strength,
        output_name=output_name,
    )


@mcp.tool()
async def unload_model() -> dict:
    """Free the model's memory now instead of waiting for the idle timeout."""
    return await _run(core.unload)


def main():
    parser = argparse.ArgumentParser(description="Z-Image MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
