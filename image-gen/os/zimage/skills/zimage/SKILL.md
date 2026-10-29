---
name: zimage
description: >-
  Local text-to-image and img2img with Z-Image-Turbo (Tongyi-MAI, 6B), running natively on Apple Silicon via MLX.
  Use when the user wants to generate, draw, render or create an image, picture, illustration, photo, poster, icon
  or concept art from a prompt, or make variations of an existing image.
---

# Z-Image-Turbo

Runs locally, no cost per image. Prefer the MCP tools (`zimage` server). Fall back to the HTTP API if MCP is not
connected.

Tool dir: `image-gen/os/zimage`

## 0. First use: download the model

The weights are not in git. Call `check_health` first. If `weights_ready` is false, this is the first use on this
machine. Tell the user the model has to be downloaded from Hugging Face (~33 GB, then quantized to a 10 GB copy;
often 30 minutes or more). Then run this **in the background** rather than letting `generate_image` do it, because a
call that long can time out:

```bash
uv run --directory image-gen/os/zimage zimage-prepare
```

Poll `check_health` every minute or two until `weights_ready` is true, then generate. Only the first use needs this.

## MCP

- `generate_image` writes PNGs and returns their paths:
  ```json
  {"prompt": "A cozy ramen shop at night, steam rising, neon sign reading \"RAMEN\", cinematic, 35mm", "width": 1344, "height": 768, "output_name": "ramen"}
  ```
  Returns `{"images": [{"path": ".../outputs/ramen.png", "seed": 123, "generation_time_s": 19.4}], ...}`. Open it on
  macOS with `open <path>`, or read the file to look at it.
- Variations: `{"prompt": "...", "count": 4}`; reproduce one later with its returned `seed`.
- Variations of an existing image: `{"prompt": "...", "image_path": "/abs/in.png", "image_strength": 0.4}`. Higher
  strength keeps more of the original (0.4 keeps the layout; 0.2 changes it more). img2img does not do strong style
  transfer (photo to watercolor, for example). For a new style, write a fresh text prompt instead.
- `unload_model` frees ~11 GB of memory right away; otherwise it unloads after 15 idle minutes.

Prompt tips:
- Be specific: subject, setting, lighting, lens/style, mood. Z-Image follows long prompts well.
- It renders English and Chinese text; put the exact words in quotes.
- Describe only what should be in the image. Turbo has no negative prompt, so a phrase like "no cash" or "no text"
  can add the object it names. Leave such phrases out and describe the scene positively instead (for example "the
  table holds only a coffee mug"). Check every result for unwanted objects before handing it over.
- Sizes: 1024x1024 square, 1344x768 landscape, 768x1344 portrait. Larger than ~1600 px per side gets slow.
- Keep `steps` at 9 unless the user wants a faster draft (6).

Notes:
- A 1024x1024 image takes about 16 s on this M5 Max; the first call in a session also loads the model (~5 s).
- Weights are Apache-2.0, so commercial use is allowed.

## HTTP fallback

```bash
uv run --directory image-gen/os/zimage zimage-api   # :8130
curl -s localhost:8130/generate -H 'Content-Type: application/json' -d '{"prompt":"a red fox in snow"}'
curl -s -F prompt='warmer evening light' -F image=@in.png localhost:8130/img2img
```

Details: `docs/MCP.md`, `docs/API.md`.
