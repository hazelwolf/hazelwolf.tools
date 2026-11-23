# Agent configs

Launch via `uv run --directory` so the tool venv is used. Secrets are not inlined; the tool reads `tools/.env`.

Tool directory: `image-gen/os/imagegen`

The weights are not in git. The tool downloads them on first use (~33 GB from Hugging Face, quantized to a 10 GB
copy), but a call that long can hit an agent's MCP timeout, so fetch them once before connecting an agent:

```bash
uv run --directory image-gen/os/imagegen imagegen-prepare
```

## Claude Code

```bash
claude mcp add imagegen -- uv run --directory image-gen/os/imagegen imagegen-mcp
```

Or `.mcp.json`:

```json
{
  "mcpServers": {
    "imagegen": {
      "command": "uv",
      "args": ["run", "--directory", "image-gen/os/imagegen", "imagegen-mcp"]
    }
  }
}
```

Skill symlink: `tools/.claude/skills/imagegen` → `image-gen/os/imagegen/skills/imagegen`. Invoke as `/imagegen`.

## Cursor

`.cursor/mcp.json` (project or user):

```json
{
  "mcpServers": {
    "imagegen": {
      "command": "uv",
      "args": ["run", "--directory", "image-gen/os/imagegen", "imagegen-mcp"]
    }
  }
}
```

Skill symlink: `tools/.cursor/skills/imagegen` → `image-gen/os/imagegen/skills/imagegen`.

## OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "imagegen": {
      "type": "local",
      "command": ["uv", "run", "--directory", "image-gen/os/imagegen", "imagegen-mcp"]
    }
  }
}
```

Point OpenCode's skill directory at `image-gen/os/imagegen/skills/imagegen`, or reuse the `.claude/skills/imagegen` symlink.

## Pi

Add an MCP server entry whose command is:

```text
uv run --directory image-gen/os/imagegen imagegen-mcp
```

Reference the skill at `image-gen/os/imagegen/skills/imagegen/SKILL.md`.
