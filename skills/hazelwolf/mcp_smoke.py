# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.28.1,<2"]
# ///
"""Smoke-test every tool's MCP server over stdio, the way Claude Code launches it.

For each tool with a `<tool>-mcp` entrypoint: start `uv run --directory <tool dir> <tool>-mcp`, initialize, list the
tools and call the read-only health tool. Nothing is generated, so no model is loaded.

hw test [tool ...]      (= uv run --script mcp_smoke.py <workspace root> [tool ...])
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Claude Code gives a stdio server 30 s to connect (MCP_TIMEOUT); slower starts show as "Failed to connect".
CONNECT_BUDGET_S = 30.0
TIMEOUT_S = 120.0
HEALTH_TOOLS = ("check_health", "health", "list_destinations")


def tools_with_mcp(root: Path) -> list[tuple[str, Path]]:
    found = []
    for skill in sorted(root.glob("*/*/*/skills/*/SKILL.md")):
        tool_dir = skill.parents[2]
        name = skill.parent.name
        pyproject = tool_dir / "pyproject.toml"
        if name == tool_dir.name and pyproject.is_file():
            if re.search(rf"^{re.escape(name)}-mcp\s*=", pyproject.read_text(), re.M):
                found.append((name, tool_dir))
    return found


async def check(name: str, tool_dir: Path) -> dict:
    params = StdioServerParameters(
        command="uv", args=["run", "--quiet", "--frozen", "--directory", str(tool_dir), f"{name}-mcp"]
    )
    # Server logs go to /dev/null so the report stays readable; startup failures still surface as exceptions.
    with open(os.devnull, "w") as devnull:
        return await _check(params, devnull)


async def _check(params: StdioServerParameters, errlog) -> dict:
    t0 = time.perf_counter()
    async with stdio_client(params, errlog=errlog) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        connect_s = time.perf_counter() - t0
        tools = [t.name for t in (await session.list_tools()).tools]
        health_tool = next((t for t in HEALTH_TOOLS if t in tools), None)
        health = None
        if health_tool:
            res = await session.call_tool(health_tool, {})
            text = "".join(getattr(c, "text", "") for c in res.content)
            health = {"tool": health_tool, "error": res.isError, "result": text}
    return {"connect_s": round(connect_s, 1), "tools": tools, "health": health}


async def main() -> int:
    root = Path(sys.argv[1]).resolve()
    only = set(sys.argv[2:])
    targets = [(n, d) for n, d in tools_with_mcp(root) if not only or n in only]
    failed = 0
    for name, tool_dir in targets:
        print(f"== {name}  ({tool_dir.relative_to(root)})", flush=True)
        try:
            r = await asyncio.wait_for(check(name, tool_dir), TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 - report any failure and move on to the next server
            failed += 1
            msg = str(e) or type(e).__name__
            if sub := getattr(e, "exceptions", None):  # ExceptionGroup from the anyio task group
                msg = "; ".join(str(x) or type(x).__name__ for x in sub)
            print(f"   FAIL  {msg}")
            continue
        slow = r["connect_s"] > CONNECT_BUDGET_S
        h = r["health"]
        bad = slow or (h is not None and h["error"])
        failed += bad
        note = "  (over the 30 s budget)" if slow else ""
        print(f"   {'FAIL' if bad else 'ok  '}  connected in {r['connect_s']} s{note}")
        print(f"   tools: {', '.join(r['tools'])}")
        if h:
            try:
                summary = json.dumps(json.loads(h["result"]), separators=(",", ":"))[:300]
            except ValueError:
                summary = h["result"][:300]
            print(f"   {h['tool']}{' ERROR' if h['error'] else ''}: {summary}")
    print(f"\n{len(targets) - failed}/{len(targets)} MCP servers ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
