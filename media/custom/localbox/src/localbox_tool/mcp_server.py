"""MCP server. stdio by default; --transport streamable-http for HTTP."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from . import core

mcp = FastMCP("localbox", host=core.bind_host(), port=core.bind_port() + 1)


@mcp.tool()
def list_destinations() -> dict:
    """List upload destination tags and the absolute folders they write to.
    The default tag is `comfy` when it is configured (ComfyUI input)."""
    return {"default": core.default_tag(), "destinations": core.destination_rows()}


@mcp.tool()
def save_file(source_path: str, destination: str = "comfy") -> dict:
    """Copy an image or video that already exists on this machine into a destination folder.
    `destination` is a tag from list_destinations (default `comfy` -> ComfyUI input).
    Keeps the original filename; if that name exists, appends -2, -3, and so on.
    Returns tag, saved path, filename, and byte size."""
    try:
        return core.save_path(destination, source_path)
    except core.LocalboxError as exc:
        raise ValueError(str(exc)) from None


def main():
    parser = argparse.ArgumentParser(description="Localbox MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
