---
name: ltx
description: >-
  Local text-to-video and image-to-video with synchronized audio using LTX-2.5 (Lightricks, 22B), running natively
  on Apple Silicon via MLX. Use when the user wants to generate, create or render a video, clip, animation, b-roll
  or short scene from a prompt, or animate a still image into a video.
---

# LTX-2.5 video

Runs locally, no cost per clip, but each clip takes a while: about 70 s for 5 s at 768x512 on this M5 Max, much longer for HD. Prefer the MCP tools (`ltx` server). Fall back to the
HTTP API if MCP is not connected.

Tool dir: `video-gen/os/ltx`

## 0. First use: download the model

The weights are not in git, and the model pack is **gated** on Hugging Face. Call `check_health` first.

- `weights_ready: false` and `hf_token_set: false`: stop and ask the user to (1) accept the LTX-2.x Community
  License at https://huggingface.co/dgrauet/ltx-2.5-mlx-q8 with their Hugging Face account and (2) put a read
  token in `tools/.env` as `HF_TOKEN=...` (or run `hf auth login`). Never ask for the token in chat; they set it
  themselves.
- `weights_ready: false` with a token: tell the user the model downloads now (~45 GB, often an hour or more), then
  run this **in the background** rather than letting `generate_video` do it:

  ```bash
  uv run --directory video-gen/os/ltx ltx-prepare
  ```

  Poll `check_health` every few minutes until `weights_ready` is true. Only the first use needs this.

## MCP

- `generate_video` writes an MP4 (video + stereo audio) and returns its path:
  ```json
  {"prompt": "A barista pours latte art in a sunlit cafe, slow push-in on the cup, steam rising; soft jazz and the hiss of the espresso machine.", "duration_s": 5, "output_name": "latte"}
  ```
  Returns `{"path": ".../outputs/latte.mp4", "duration_s": 5.04, "seed": 123, "generation_time_s": ..., ...}`.
  Open it on macOS with `open <path>`.
- Animate a still: add `"image_path": "/abs/frame.png"` (it becomes the first frame; match its aspect ratio with
  `width`/`height`). Images from the `zimage` tool work well here.
- `duration_s: null` lets the model choose a length (1–20 s) from the prompt.
- `unload_model` frees memory right away; otherwise the pipeline unloads after 10 idle minutes.

Prompt tips:
- Write one flowing paragraph, in order: subject and action, camera move (static, slow push-in, pan, handheld),
  lighting and style, then sound (dialogue in quotes, ambience, music). LTX-2.5 generates the audio from it.
- Describe what should happen; there is no negative prompt in this mode, so "no text" can add text.
- Sizes: 768x512 landscape (default, fastest), 512x768 portrait, 1280x704 HD (much slower). Sides snap to
  multiples of 64.
- Start with short clips (3–5 s) to iterate; time grows with resolution × duration.

Notes:
- Tell the user before starting that a clip takes minutes, and don't start several at once: they run one at a time.
- Weights license: LTX-2.x Community License. Free (including commercial use) for entities under $10M annual
  revenue; larger companies need a paid license from Lightricks. For Apache-licensed video, use the `wan` tool
  (no audio, about 10x slower).

## HTTP fallback

```bash
uv run --directory video-gen/os/ltx ltx-api   # :8140
curl -s localhost:8140/generate -H 'Content-Type: application/json' -d '{"prompt":"waves at sunset","duration_s":4}'
curl -s -F prompt='the camera slowly pushes in' -F image=@frame.png -F duration_s=4 localhost:8140/img2video
```

Details: `docs/MCP.md`, `docs/API.md`.
