# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; the tool reads `tools/.env`.

Tool directory: `audio-gen/os/voicestudio`

Before any agent call, start the backend (it keeps models warm):

```bash
uv run --directory audio-gen/os/voicestudio voicestudio-backend
```

## Claude Code

```bash
claude mcp add voicestudio -- uv run --directory audio-gen/os/voicestudio voicestudio-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "voicestudio": {
      "command": "uv",
      "args": ["run", "--directory", "audio-gen/os/voicestudio", "voicestudio-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/voicestudio` → `audio-gen/os/voicestudio/skills/voicestudio`. Invoke as `/voicestudio`.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "voicestudio": {
      "command": "uv",
      "args": ["run", "--directory", "audio-gen/os/voicestudio", "voicestudio-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/voicestudio` → `audio-gen/os/voicestudio/skills/voicestudio`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "voicestudio": {
      "type": "local",
      "command": ["uv", "run", "--directory", "audio-gen/os/voicestudio", "voicestudio-mcp"]
    }
  }
}
```

Point OpenCode's skill directory at `audio-gen/os/voicestudio/skills/voicestudio`, or reuse the `.claude/skills/voicestudio` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory audio-gen/os/voicestudio voicestudio-mcp
```

Reference the skill at `audio-gen/os/voicestudio/skills/voicestudio/SKILL.md`.
