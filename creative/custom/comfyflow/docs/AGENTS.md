# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; comfyflow reads `tools/.env`.

Tool directory: `creative/custom/comfyflow`, relative to the repo root. Run the commands below from the repo root, or swap in an absolute path if your client starts MCP servers from somewhere else.

## Claude Code

```bash
claude mcp add comfyflow -- uv run --directory creative/custom/comfyflow comfyflow-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "comfyflow": {
      "command": "uv",
      "args": ["run", "--directory", "creative/custom/comfyflow", "comfyflow-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/comfyflow` → `creative/custom/comfyflow/skills/comfyflow`. Invoke as `/comfyflow`.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "comfyflow": {
      "command": "uv",
      "args": ["run", "--directory", "creative/custom/comfyflow", "comfyflow-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/comfyflow` → `creative/custom/comfyflow/skills/comfyflow`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "comfyflow": {
      "type": "local",
      "command": ["uv", "run", "--directory", "creative/custom/comfyflow", "comfyflow-mcp"]
    }
  }
}
```

Point OpenCode’s skill directory at `creative/custom/comfyflow/skills/comfyflow`, or reuse the `.claude/skills/comfyflow` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory creative/custom/comfyflow comfyflow-mcp
```

Reference the skill at `creative/custom/comfyflow/skills/comfyflow/SKILL.md`.
