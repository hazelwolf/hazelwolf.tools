"""MCP server (stdio by default; --transport streamable-http for HTTP).

Images move by file path, never base64, so nothing large enters the agent's context.
"""

from __future__ import annotations

import argparse

import anyio
from mcp.server.fastmcp import FastMCP

from . import config, core

mcp = FastMCP("imagegen", host=config.API_HOST, port=config.MCP_PORT)


async def _run(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except core.ServiceError as e:
        raise ValueError(str(e)) from None


@mcp.tool()
async def check_health() -> dict:
    """Check the imagegen tool: whether each model's weights are downloaded (models.<name>.weights_ready; the top-level weights_ready is Z-Image's), which model is loaded, its quantization and where outputs go.

    If a model's weights_ready is false, its first use must download and quantize it (Z-Image ~33 GB, Boogu ~39 GB). Run `uv run --directory <tool dir> imagegen-prepare --model <zimage|boogu>` in the background and wait for weights_ready, because generate_image would otherwise do it inside one long call."""
    return await _run(core.health)


@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    seed: int | None = None,
    count: int = 1,
    image_path: str | None = None,
    image_strength: float | None = None,
    output_name: str | None = None,
    model: str = "zimage",
) -> dict:
    """Text to image, locally on this Mac, with Z-Image-Turbo (default) or Boogu Image Turbo. Writes PNGs to the tool's outputs/ folder and returns their absolute paths.

    Pick the model by what the image is for:
    - model="zimage" (default): people, faces, hands, photos, products, scenes, illustrations and art styles, and anything with only a word or two of text. About 16-19 s per 1024x1024 image.
    - model="boogu": text-heavy images where the words must be right and are the point: signs, posters, book covers, menus, labels, packaging, infographics, UI screens, multiple lines of text, or Chinese text. About 60 s per 1024x1024 image, and no img2img.

    Args:
        prompt: What to draw. Detailed prompts (subject, setting, lighting, style, camera) work best. Put the exact words to render in quotes.
        width: 256-2048, rounded down to a multiple of 16. 1024x1024 by default; e.g. 1344x768 landscape, 768x1344 portrait.
        height: 256-2048, rounded down to a multiple of 16.
        steps: Denoising steps. Default is the model's own (zimage 9, boogu 8); fewer is faster and softer. Boogu at 768 px or less is fine with 4.
        seed: Fix for reproducible output; random if omitted (the seed used is returned).
        count: 1-8 images, seeds seed, seed+1, ...
        image_path: Optional local init image for img2img variations. It keeps the layout but does not do strong style transfer.
        image_strength: img2img only, 0-1: how much of the init image to keep (default 0.4; 0.2 changes more).
        output_name: Output file stem.
        model: "zimage" (default) or "boogu", see above. Only one model is held in memory; switching unloads the other, and the first Boogu image after a switch is slower while its weights load.

    On a model's first use (check_health models.<name>.weights_ready=false) this call first downloads and quantizes its weights, which can take 30-60 minutes.
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
        model=model,
    )


@mcp.tool()
async def unload_model() -> dict:
    """Free the model's memory now instead of waiting for the idle timeout."""
    return await _run(core.unload)


def main():
    parser = argparse.ArgumentParser(description="imagegen MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
