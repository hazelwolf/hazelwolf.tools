# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; the tool reads `tools/.env`.

Tool directory: `image-gen/os/zimage`

The weights are not in git. The tool downloads them on first use (~33 GB from Hugging Face, quantized to a 10 GB
copy), but a call that long can hit an agent's MCP timeout, so fetch them once before connecting an agent:

```bash
uv run --directory image-gen/os/zimage zimage-prepare
```

## Claude Code

```bash
claude mcp add zimage -- uv run --directory image-gen/os/zimage zimage-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "zimage": {
      "command": "uv",
      "args": ["run", "--directory", "image-gen/os/zimage", "zimage-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/zimage` → `image-gen/os/zimage/skills/zimage`. Invoke as `/zimage`.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "zimage": {
      "command": "uv",
      "args": ["run", "--directory", "image-gen/os/zimage", "zimage-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/zimage` → `image-gen/os/zimage/skills/zimage`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "zimage": {
      "type": "local",
      "command": ["uv", "run", "--directory", "image-gen/os/zimage", "zimage-mcp"]
    }
  }
}
```

Point OpenCode's skill directory at `image-gen/os/zimage/skills/zimage`, or reuse the `.claude/skills/zimage` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory image-gen/os/zimage zimage-mcp
```

Reference the skill at `image-gen/os/zimage/skills/zimage/SKILL.md`.
