# MCP server

```bash
uv run --directory <tool dir> imagegen-mcp                               # stdio (default)
uv run --directory <tool dir> imagegen-mcp --transport streamable-http   # http://127.0.0.1:8131/mcp
```

**Two models.** `model: "zimage"` (default, Z-Image-Turbo) for people, photos, scenes and art styles;
`model: "boogu"` (Boogu Image Turbo) for text-heavy images: posters, menus, labels, book covers, several lines of
text. Boogu takes ~60 s per 1024x1024 image against Z-Image's ~16-19 s, and has no img2img.

**First use:** if `check_health` returns `models.<name>.weights_ready: false`, that model's weights are not on disk
yet. The first `generate_image` call with it would download (Z-Image ~33 GB, Boogu ~39 GB) and quantize them before
generating, which can take 30-60 minutes and outlast the client's timeout. Run
`uv run --directory <tool dir> imagegen-prepare --model <zimage|boogu>` in the background instead, and wait for
`weights_ready: true`.

The model runs inside the MCP process. One model is held at a time: it loads on the first `generate_image` call that
asks for it, is swapped out when a call asks for the other one, and is freed after `IMAGEGEN_IDLE_UNLOAD_S` idle
seconds (900 by default), or right away with `unload_model`.

Images go in and out as **local file paths**, so no base64 enters the agent's context.

## Tools

| Tool | Params | Returns |
|---|---|---|
| `check_health` | – | `{weights_ready, models: {zimage: {weights_ready, path, default_steps, img2img}, boogu: {...}}, loaded, loaded_model, quantize, load_time_s, output_dir, ...}` |
| `generate_image` | `prompt`, `width=1024`, `height=1024`, `steps?` (model default: zimage 9, boogu 8), `seed?`, `count=1`, `image_path?`, `image_strength?`, `output_name?`, `model="zimage"` | `{model, images: [{path, name, seed, generation_time_s}], width, height, steps, quantize}` |
| `unload_model` | – | `{unloaded}` |

Examples:

```json
{"tool": "generate_image", "arguments": {"prompt": "A neon sign reading \"OPEN LATE\" above a rainy Tokyo alley, cinematic", "width": 1344, "height": 768}}
{"tool": "generate_image", "arguments": {"prompt": "isometric cozy reading room, soft light", "seed": 7, "count": 4}}
{"tool": "generate_image", "arguments": {"prompt": "A book cover titled \"The Silent Orchard\" by \"Mira Holt\", minimalist apple tree", "model": "boogu"}}
{"tool": "generate_image", "arguments": {"prompt": "a variation with warmer evening light", "image_path": "/Users/me/photo.png", "image_strength": 0.4}}
```

Errors come back as tool errors with a plain message (for example "width must be between 256 and 2048", or
"boogu does not support img2img; use model='zimage' for image variations").

## Environment

Read from `tools/.env`: `IMAGEGEN_QUANTIZE`, `IMAGEGEN_MODEL_PATH`, `IMAGEGEN_BOOGU_MODEL_PATH`, `IMAGEGEN_OUTPUT_DIR`, `IMAGEGEN_IDLE_UNLOAD_S`,
`IMAGEGEN_MLX_CACHE_LIMIT_GB`, `IMAGEGEN_MCP_PORT`. See the README.

## Testing

```bash
npx @modelcontextprotocol/inspector uv run --directory <tool dir> imagegen-mcp
```
