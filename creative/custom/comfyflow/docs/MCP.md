# MCP

Seven tools, all thin wrappers over `comfyflow_tool.core`.

stdio (default):

```bash
uv run --directory creative/custom/comfyflow comfyflow-mcp
```

Streamable HTTP or SSE (port is `COMFYFLOW_PORT + 1`, default `8131`):

```bash
uv run --directory creative/custom/comfyflow comfyflow-mcp --transport streamable-http
```

Environment comes from `tools/.env` (`COMFYFLOW_*`). ComfyUI must be running.

| Tool | Arguments | Returns |
|---|---|---|
| `health` | none | ComfyUI version, GPU, free VRAM, workflow count |
| `list_workflows` | none | name, description, parameter names |
| `describe_workflow` | `name` | parameters with type, default, description; output nodes |
| `run_workflow` | `name`, `params`, `wait` (true), `timeout_s`, `randomize_seed` (true) | status, `files` (absolute paths, kind image/video/audio), `seeds`, `error` |
| `get_job` | `prompt_id` | queued / running / success / error, with files when finished |
| `cancel_job` | `prompt_id` | cancels a queued job or interrupts the running one |
| `import_workflow` | `name`, `prompt_id`, `description`, `overwrite` | saves the last ComfyUI run as a workflow and describes it |

Typical call:

```json
{"name": "z_image_turbo", "params": {"prompt": "a lighthouse in a storm", "size.width": 1024, "size.height": 1024}}
```

Image runs take about 12 s, video 1-3 min on the 12 GB GPU. Use `wait: false` and `get_job` for video. Errors come back as MCP tool errors with the reason (unknown parameter, ComfyUI validation message, ComfyUI not running).

Inspect with MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run --directory creative/custom/comfyflow comfyflow-mcp
```
