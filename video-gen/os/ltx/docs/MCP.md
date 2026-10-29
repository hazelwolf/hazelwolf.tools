# MCP server

```bash
uv run --directory <tool dir> ltx-mcp                               # stdio (default)
uv run --directory <tool dir> ltx-mcp --transport streamable-http   # http://127.0.0.1:8141/mcp
```

**First use:** if `check_health` returns `weights_ready: false`, the gated model pack is not on disk yet. Accept the
LTX-2.x license on Hugging Face, set `HF_TOKEN` in `tools/.env`, then run `uv run --directory <tool dir> ltx-prepare`
in the background (~45 GB) and wait for `weights_ready: true`. Otherwise the first `generate_video` call downloads it
inside one very long call that will outlast the client's timeout.

The pipeline runs inside the MCP process, one clip at a time. It is created on the first call and freed after
`LTX_IDLE_UNLOAD_S` idle seconds (600 by default), or right away with `unload_model`.

Videos go in and out as **local file paths**, so no base64 enters the agent's context.

## Tools

| Tool | Params | Returns |
|---|---|---|
| `check_health` | – | `{weights_ready, hf_token_set, loaded, low_ram, output_dir, ...}` |
| `generate_video` | `prompt`, `width=768`, `height=512`, `duration_s=5` (or `null` = model picks), `fps=24`, `seed?`, `image_path?`, `output_name?` | `{path, name, seed, width, height, fps, frames, duration_s, audio, generation_time_s, peak_memory_gb}` |
| `unload_model` | – | `{unloaded}` |

Examples:

```json
{"tool": "generate_video", "arguments": {"prompt": "Waves roll onto a quiet beach at golden hour, slow pan right, gulls calling", "duration_s": 4}}
{"tool": "generate_video", "arguments": {"prompt": "She turns toward the window and smiles; soft morning birdsong", "image_path": "/Users/me/still.png", "width": 768, "height": 512}}
{"tool": "generate_video", "arguments": {"prompt": "A heavy wooden door creaks slowly open", "duration_s": null}}
```

Errors come back as tool errors with a plain message (for example the gated-license instructions, or "duration_s
must be between 1 and 20").

## Timeouts

A clip takes minutes. MCP clients with a short tool timeout will give up before it finishes; for Claude Code, raise
it with `MCP_TOOL_TIMEOUT` (milliseconds) in the environment that launches it. The clip still finishes and lands in
`outputs/` either way.

## Environment

Read from `tools/.env`: `HF_TOKEN`, `LTX_HF_REPO`, `LTX_MODEL_PATH`, `LTX_LOW_RAM`, `LTX_OUTPUT_DIR`,
`LTX_IDLE_UNLOAD_S`, `LTX_MCP_PORT`. See the README.

## Testing

```bash
npx @modelcontextprotocol/inspector uv run --directory <tool dir> ltx-mcp
```
