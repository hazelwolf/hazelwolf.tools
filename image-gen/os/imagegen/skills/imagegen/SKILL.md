---
name: imagegen
description: >-
  Local text-to-image and img2img on Apple Silicon via MLX, with two models: Z-Image-Turbo (Tongyi-MAI, 6B) for
  people, photos, scenes and art styles, and Boogu Image Turbo (10B) for text-heavy images such as signs, posters,
  menus, labels and book covers. Use when the user wants to generate, draw, render or create an image, picture,
  illustration, photo, poster, icon or concept art from a prompt, or make variations of an existing image.
---

# imagegen: Z-Image-Turbo + Boogu Image Turbo

Runs locally, no cost per image. Prefer the MCP tools (`imagegen` server). Fall back to the HTTP API if MCP is not
connected.

Tool dir: `image-gen/os/imagegen`

## Pick the model

Pass `model` to `generate_image`. The choice comes from a blind comparison of the two (`evals/image-gen`):

| Image | `model` | Why |
|---|---|---|
| People, faces, hands, portraits, groups | `zimage` (default) | Strong anatomy and skin; 3-4x faster |
| Photos, products, food, landscapes, scenes | `zimage` | Same quality, much faster |
| Illustration and art styles (watercolour, vector, pixel art, anime) | `zimage` | |
| A word or two of text in a scene (a shop sign in a street photo) | `zimage` | Renders short text well |
| **Text-heavy**: posters, flyers, book covers, menus, price lists, labels, packaging, infographics, UI screens, several lines of text, Chinese text | `boogu` | Gets long and multi-line text right |
| Variations of an existing image (img2img) | `zimage` | Boogu has no img2img |

The test: if the image fails when a word is misspelled, use `boogu`. When unsure, use `zimage`. Each image takes
16-19 s with `zimage` and ~60 s with `boogu`, so tell the user a Boogu image takes about a minute.

## 0. First use: download the model

The weights are not in git. Call `check_health` first and look at `models.<name>.weights_ready` for the model you
picked. If it is false, that model's first use on this machine needs a download from Hugging Face (Z-Image ~33 GB
→ 10 GB copy; Boogu ~39 GB → 19 GB copy; often 30-60 minutes). Tell the user, then run this **in the background**
rather than letting `generate_image` do it, because a call that long can time out:

```bash
uv run --directory image-gen/os/imagegen imagegen-prepare                 # Z-Image
uv run --directory image-gen/os/imagegen imagegen-prepare --model boogu   # Boogu
```

Poll `check_health` every minute or two until that model's `weights_ready` is true, then generate. Only the first
use of each model needs this.

## MCP

- `generate_image` writes PNGs and returns their paths:
  ```json
  {"prompt": "A cozy ramen shop at night, steam rising, neon sign reading \"RAMEN\", cinematic, 35mm", "width": 1344, "height": 768, "output_name": "ramen"}
  ```
  Returns `{"model": "zimage", "images": [{"path": ".../outputs/ramen.png", "seed": 123, "generation_time_s": 19.4}], ...}`.
  Open it on macOS with `open <path>`, or read the file to look at it.
- Text-heavy image with Boogu:
  ```json
  {"prompt": "A coffee shop chalkboard menu listing \"Espresso 3.00\", \"Latte 4.50\" and \"Mocha 5.00\" in white chalk handwriting", "model": "boogu"}
  ```
- Variations: `{"prompt": "...", "count": 4}`; reproduce one later with its returned `seed`.
- Variations of an existing image: `{"prompt": "...", "image_path": "/abs/in.png", "image_strength": 0.4}`. Higher
  strength keeps more of the original (0.4 keeps the layout; 0.2 changes it more). img2img does not do strong style
  transfer (photo to watercolor, for example). For a new style, write a fresh text prompt instead.
- `unload_model` frees the loaded model's memory right away (Z-Image ~11 GB, Boogu ~30 GB); otherwise it unloads
  after 15 idle minutes. Only one model is held at a time: asking for the other one swaps it in, so group Boogu
  requests together instead of alternating.

Prompt tips:
- Be specific: subject, setting, lighting, lens/style, mood. Z-Image follows long prompts well.
- Put the exact words to render in quotes. For more than a short phrase, use `model: "boogu"`.
- Describe only what should be in the image. Turbo has no negative prompt, so a phrase like "no cash" or "no text"
  can add the object it names. Leave such phrases out and describe the scene positively instead (for example "the
  table holds only a coffee mug"). Check every result for unwanted objects before handing it over.
- Sizes: 1024x1024 square, 1344x768 landscape, 768x1344 portrait. Larger than ~1600 px per side gets slow.
- Leave `steps` unset: each model uses its own (Z-Image 9, Boogu 8). For a faster Z-Image draft use 6; Boogu at
  768 px or smaller is fine with 4.

Notes:
- 1024x1024 on this M5 Max: Z-Image ~16-19 s, Boogu ~60 s (up to ~95 s). A model switch adds a few seconds of
  loading.
- Both models' weights are Apache-2.0, so commercial use is allowed.

## HTTP fallback

```bash
uv run --directory image-gen/os/imagegen imagegen-api   # :8130
curl -s localhost:8130/generate -H 'Content-Type: application/json' -d '{"prompt":"a red fox in snow"}'
curl -s localhost:8130/generate -H 'Content-Type: application/json' -d '{"prompt":"a poster reading \"GRAND OPENING\"","model":"boogu"}'
curl -s -F prompt='warmer evening light' -F image=@in.png localhost:8130/img2img
```

Details: `docs/MCP.md`, `docs/API.md`.
