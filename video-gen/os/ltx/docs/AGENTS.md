# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; the tool reads `tools/.env`.

Tool directory: `video-gen/os/ltx`

The weights are not in git, and the pack is gated. Accept the LTX-2.x license at
https://huggingface.co/dgrauet/ltx-2.5-mlx-q8, put `HF_TOKEN` in `tools/.env`, then fetch them once (~45 GB) before
connecting an agent:

```bash
uv run --directory video-gen/os/ltx ltx-prepare
```

A clip takes minutes, so give the agent a long MCP tool timeout (Claude Code: `MCP_TOOL_TIMEOUT`, in ms).

## Claude Code

```bash
claude mcp add ltx -- uv run --directory video-gen/os/ltx ltx-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "ltx": {
      "command": "uv",
      "args": ["run", "--directory", "video-gen/os/ltx", "ltx-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/ltx` → `video-gen/os/ltx/skills/ltx`. Invoke as `/ltx`. From other projects,
`skills/hazelwolf/hw install` registers it at user scope with the other tools.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "ltx": {
      "command": "uv",
      "args": ["run", "--directory", "video-gen/os/ltx", "ltx-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/ltx` → `video-gen/os/ltx/skills/ltx`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "ltx": {
      "type": "local",
      "command": ["uv", "run", "--directory", "video-gen/os/ltx", "ltx-mcp"]
    }
  }
}
```

Point OpenCode's skill directory at `video-gen/os/ltx/skills/ltx`, or reuse the `.claude/skills/ltx` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory video-gen/os/ltx ltx-mcp
```

Reference the skill at `video-gen/os/ltx/skills/ltx/SKILL.md`.
