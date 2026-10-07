# MCP

Two tools, both thin wrappers over `localbox_tool.core`.

## Transport

stdio (default):

```bash
uv run --directory /home/bhomit/Dev/genai/tools/media/custom/localbox localbox-mcp
```

Streamable HTTP or SSE (port is `LOCALBOX_PORT + 1`, default `8121`, so it does not take the page’s port):

```bash
uv run --directory /home/bhomit/Dev/genai/tools/media/custom/localbox localbox-mcp --transport streamable-http
```

Inspect with MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run --directory /home/bhomit/Dev/genai/tools/media/custom/localbox localbox-mcp
```

Environment comes from `tools/.env` (`LOCALBOX_DESTINATIONS`, `LOCALBOX_MAX_MB`, `LOCALBOX_HOST`, `LOCALBOX_PORT`).

## list_destinations

No arguments. Returns the default tag and each tag’s absolute folder.

```json
{
  "default": "comfy",
  "destinations": [
    {"tag": "comfy", "path": "/home/bhomit/Dev/genai/ComfyUI/input", "default": true}
  ]
}
```

## save_file

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `source_path` | string | required | Image or video that already exists on this machine |
| `destination` | string | `comfy` | Tag from `list_destinations` |

Copies the file into that folder. Same suffix, size, empty-file, and `-2`/`-3` naming rules as the HTTP upload. The source file is left in place.

```json
{
  "tag": "comfy",
  "path": "/home/bhomit/Dev/genai/ComfyUI/input/clip.mp4",
  "name": "clip.mp4",
  "bytes": 999
}
```

Failures raise `ValueError` with the same message the API returns in `error`.
