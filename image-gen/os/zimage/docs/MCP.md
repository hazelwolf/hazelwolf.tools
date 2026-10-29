# MCP server

```bash
uv run --directory <tool dir> zimage-mcp                               # stdio (default)
uv run --directory <tool dir> zimage-mcp --transport streamable-http   # http://127.0.0.1:8131/mcp
```

**First use:** if `check_health` returns `weights_ready: false`, the weights are not on disk yet. The first
`generate_image` call would download (~33 GB) and quantize them before generating, which can take 30+ minutes and
outlast the client's timeout. Run `uv run --directory <tool dir> zimage-prepare` in the background instead, and wait
for `weights_ready: true`.

The model runs inside the MCP process. It loads on the first `generate_image` call and is freed after
`ZIMAGE_IDLE_UNLOAD_S` idle seconds (900 by default), or right away with `unload_model`.

Images go in and out as **local file paths**, so no base64 enters the agent's context.

## Tools

| Tool | Params | Returns |
|---|---|---|
| `check_health` | – | `{weights_ready, loaded, model_path, quantize, load_time_s, output_dir, ...}` |
| `generate_image` | `prompt`, `width=1024`, `height=1024`, `steps=9`, `seed?`, `count=1`, `image_path?`, `image_strength?`, `output_name?` | `{images: [{path, name, seed, generation_time_s}], width, height, steps, quantize}` |
| `unload_model` | – | `{unloaded}` |

Examples:

```json
{"tool": "generate_image", "arguments": {"prompt": "A neon sign reading \"OPEN LATE\" above a rainy Tokyo alley, cinematic", "width": 1344, "height": 768}}
{"tool": "generate_image", "arguments": {"prompt": "isometric cozy reading room, soft light", "seed": 7, "count": 4}}
{"tool": "generate_image", "arguments": {"prompt": "a variation with warmer evening light", "image_path": "/Users/me/photo.png", "image_strength": 0.4}}
```

Errors come back as tool errors with a plain message (for example "width must be between 256 and 2048").

## Environment

Read from `tools/.env`: `ZIMAGE_QUANTIZE`, `ZIMAGE_MODEL_PATH`, `ZIMAGE_OUTPUT_DIR`, `ZIMAGE_IDLE_UNLOAD_S`,
`ZIMAGE_MLX_CACHE_LIMIT_GB`, `ZIMAGE_MCP_PORT`. See the README.

## Testing

```bash
npx @modelcontextprotocol/inspector uv run --directory <tool dir> zimage-mcp
```
