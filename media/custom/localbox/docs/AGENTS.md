# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; localbox reads `tools/.env`.

Tool directory: `media/custom/localbox`

## Claude Code

```bash
claude mcp add localbox -- uv run --directory media/custom/localbox localbox-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "localbox": {
      "command": "uv",
      "args": ["run", "--directory", "media/custom/localbox", "localbox-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/localbox` → `media/custom/localbox/skills/localbox`. Invoke as `/localbox`.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "localbox": {
      "command": "uv",
      "args": ["run", "--directory", "media/custom/localbox", "localbox-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/localbox` → `media/custom/localbox/skills/localbox`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "localbox": {
      "type": "local",
      "command": ["uv", "run", "--directory", "media/custom/localbox", "localbox-mcp"]
    }
  }
}
```

Point OpenCode’s skill directory at `media/custom/localbox/skills/localbox`, or reuse the `.claude/skills/localbox` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory media/custom/localbox localbox-mcp
```

Reference the skill at `media/custom/localbox/skills/localbox/SKILL.md`.
