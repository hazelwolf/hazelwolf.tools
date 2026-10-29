# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; the tool reads `tools/.env`.

Tool directory: `video-gen/os/wan`

The weights are not in git. Fetch them once (~18 GB, not gated) before connecting an agent:

```bash
uv run --directory video-gen/os/wan wan-prepare
```

Clips run as background jobs inside the MCP server process (`generate_video` → `get_video_job`), so no long MCP
timeout is needed. Jobs end with that process: keep the agent session open until a job finishes.

## Claude Code

```bash
claude mcp add wan -- uv run --directory video-gen/os/wan wan-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "wan": {
      "command": "uv",
      "args": ["run", "--directory", "video-gen/os/wan", "wan-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/wan` → `video-gen/os/wan/skills/wan`. Invoke as `/wan`. From other projects,
`skills/hazelwolf/hw install` registers it at user scope with the other tools.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "wan": {
      "command": "uv",
      "args": ["run", "--directory", "video-gen/os/wan", "wan-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/wan` → `video-gen/os/wan/skills/wan`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "wan": {
      "type": "local",
      "command": ["uv", "run", "--directory", "video-gen/os/wan", "wan-mcp"]
    }
  }
}
```

Point OpenCode's skill directory at `video-gen/os/wan/skills/wan`, or reuse the `.claude/skills/wan` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory video-gen/os/wan wan-mcp
```

Reference the skill at `video-gen/os/wan/skills/wan/SKILL.md`.
