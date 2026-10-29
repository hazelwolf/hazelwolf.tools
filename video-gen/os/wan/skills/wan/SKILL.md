---
name: wan
description: >-
  Local text-to-video and image-to-video with Wan 2.2 TI2V-5B (Alibaba, Apache-2.0), running natively on Apple
  Silicon via MLX. Slow (about 12 minutes per 5 s clip) but license-free for commercial use and strong at animating
  a still image. Use when the user wants a video clip without LTX's revenue-limited license, or wants a still image
  animated with Wan; for quick drafts or clips with sound, prefer the ltx tool.
---

# Wan 2.2 video

Runs locally, no cost per clip, and the weights are Apache-2.0. It is **slow**: on this M5 Max a 5 s clip takes
about 12 minutes at 832x480. It makes video only, no audio. The model's native 1280x704 does not fit this Mac's
memory, so frames are capped at 1024x576 (area). Prefer the MCP tools (`wan` server); fall back to the HTTP API.

Tool dir: `video-gen/os/wan`

## When to use which video tool

| Need | Tool |
|---|---|
| Fast drafts, clips with sound (dialogue, ambience, music) | `ltx` (~70 s per 5 s clip) |
| Commercial use at a company with $10M+ revenue, or Wan's look | `wan` |
| Animate a still (e.g. from `zimage`) | either; `wan` is often rated stronger at image-to-video |

## 0. First use

Call `check_health`. If `weights_ready` is false, run this in the background (~18 GB, not gated, no token needed)
and wait for `weights_ready: true`:

```bash
uv run --directory video-gen/os/wan wan-prepare
```

## MCP: clips run as background jobs

1. Tell the user the clip will take about 12 minutes, then queue it:
   ```json
   {"prompt": "A glass sphere floats above calm teal water at dawn, slow orbit around it, soft volumetric light", "duration_s": 5, "output_name": "sphere"}
   ```
   `generate_video` returns at once: `{"job_id": "a1b2c3d4e5f6", "status": "queued", "queue_position": 0, ...}`.
2. Follow it with `get_video_job` (`{"job_id": "a1b2c3d4e5f6"}`). It waits up to 45 s per call, so a call every
   minute is enough. While running it shows `phase` (`loading`, `start`, `denoise`, `decode`, ...) and
   `step`/`total_steps`. Give the user an occasional progress update instead of polling silently.
3. When `status` is `done`, `result.path` is the MP4. Open it on macOS with `open <path>`. On `failed`, report
   `error`.

`list_video_jobs` shows every job in this server process (lost on restart; finished files stay in `outputs/`). The
model is loaded per job and freed afterwards, so an idle server holds no GPU memory.

Options:
- Animate a still: `"image_path": "/abs/frame.png"`. The output follows the image's aspect ratio.
- `steps`: 25 by default; 50 is Wan's reference quality at about twice the time; 10–15 for a rough preview.
- Sizes: 832x480 landscape (default), 480x832 portrait, up to 1024x576 / 576x1024 / 768x768. Larger sizes are
  rejected (they would swap on 48 GB). Up to 5.04 s (121 frames at 24 fps).
- `negative_prompt` works here (Wan uses CFG); Wan's default negative prompt is applied when omitted.

Prompt tips: describe the subject and action, the camera move, lighting and style in plain sentences. Wan follows
detailed, concrete prompts well.

## HTTP fallback

```bash
uv run --directory video-gen/os/wan wan-api   # :8150
curl -s localhost:8150/generate -H 'Content-Type: application/json' -d '{"prompt":"waves at sunset","duration_s":3}'
curl -s "localhost:8150/jobs/<job_id>?wait_s=60"
```

Details: `docs/MCP.md`, `docs/API.md`.
