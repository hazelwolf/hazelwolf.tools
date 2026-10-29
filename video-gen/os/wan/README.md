# Wan 2.2 video

Local text-to-video and image-to-video for agents with [Wan 2.2 TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B)
(Alibaba, 5B, Apache-2.0). It runs natively on Apple Silicon through [mlx-gen](https://github.com/lpalbou/mlx-gen),
an MLX runtime, and ships with an HTTP API, an MCP server and the `/wan` skill.

It complements [`ltx`](../ltx/README.md). LTX-2.5 is about 10x faster here and makes audio, but its weights are
revenue-limited. Wan's weights are Apache-2.0 with no limits, and Wan is often rated stronger at image-to-video. It
is slow on a Mac, so generation runs as background jobs.

| | |
|---|---|
| Upstream | https://github.com/lpalbou/mlx-gen (submodule at `upstream/`) |
| Pinned ref | `v0.38.0` (`99fb94dd3eaa9dd1931cd3cd8eae1ae3e20f2ef3`) |
| Code license | MIT (`upstream/LICENSE`) |
| Model | [`AbstractFramework/wan2.2-ti2v-5b-diffusers-8bit`](https://huggingface.co/AbstractFramework/wan2.2-ti2v-5b-diffusers-8bit) @ `6875952` (mlx-gen's 8-bit package of `Wan-AI/Wan2.2-TI2V-5B-Diffusers`) |
| Weights license | Apache-2.0 |
| Commercial use | Yes |

## How it fits together

```
agent ── MCP (stdio) ──> wan-mcp ─┐                    ┌─ job queue ── worker thread
curl / Postman ── HTTP :8150 ──> wan-api ─┴─ core.py ──┤
                                                       └─ mlx-gen Wan2_2_TI2V (MLX, Metal GPU) ── models/huggingface
```

`generate_video` / `POST /generate` validate the request and queue a job. One worker runs jobs in order and
records the phase and step. `get_video_job` / `GET /jobs/{id}` return progress and, when done, the MP4 path. Jobs
live in memory. MP4s (H.264, 24 fps, no audio) are written to `outputs/`.

## Setup

```bash
cd video-gen/os/wan
git submodule update --init upstream     # if the clone skipped submodules
uv sync                                  # Python 3.13, MLX 0.32
uv run wan-prepare                       # recommended: fetch the weights now (~18 GB) instead of on the first job
```

### Model weights (downloaded on first use)

The weights are **not in git**: `models/` is gitignored. The package is public and not gated, so no token is
needed. The first job, or `wan-prepare`, downloads it into `models/huggingface/`, with a file lock so the API and
MCP server never download twice. Interrupted downloads resume. `check_health` reports `weights_ready`.

The package is the UMT5-XXL text encoder (11.4 GB), the 5B transformer in 8-bit (5.4 GB) and the Wan 2.2 VAE
(1.4 GB). mlx-gen dequantizes the transformer to bf16 at load, so 8-bit only saves download size. Running memory
matches the bf16 package.

## Run

```bash
uv run wan-api                           # HTTP API on 127.0.0.1:8150 (docs at /docs)
uv run wan-mcp                           # MCP over stdio (agents launch this themselves)
```

## Choices for this machine

This machine is an Apple M5 Max with 48 GB unified memory (40 GB GPU working set).

- **TI2V-5B, not A14B.** The 14B models are higher quality, but mlx-gen measured about 30 minutes for 5 s at
  480x240 on an M5 Max. TI2V-5B does text- and image-to-video in one model.
- **mlx-gen.** It's maintained (v0.38.0, September 2026), MIT, publishes Mac-tested Wan packages, and documents its
  M5 Max timings. The older `mlx-video` port has not changed since May 2026.
- **832x480, 25 steps by default.** These are mlx-gen's measured settings for this chip, with flow shift 3, its
  recommendation below 720p. 25 steps roughly halves Wan's 50-step reference time; there is no 4-step distilled
  LoRA for TI2V-5B.
- **Frames capped at 1024x576 (area).** The Wan 2.2 VAE decodes the whole frame at once. mlx-gen's spatial tiling
  is refused for this VAE ("proven only for the Wan2.1 patch-size-1 VAE"), so decode memory grows with frame
  area. Measured here on 2 s, 4-step probes:

  | Size | Default settings | With the settings this tool uses |
  |---|---|---|
  | 832x480 | 32.7 GB | **23.0 GB** |
  | 1024x576 | – | **33.3 GB** |
  | 1280x704 (native HD) | 60.6 GB, swapped, 523 s | 50.3 GB, still over 48 GB |

  So larger frames are rejected with a clear error rather than left to swap the Mac.
- **Memory settings.** Each job passes `release_denoisers_before_decode=True` (frees the transformer before the
  decode) and `clear_cache_each_step=True`. Releasing leaves that model object unusable, so every job builds a
  fresh one. That costs 2–4 s, and an idle server holds no GPU memory as a result.
- **Background jobs.** A clip takes longer than MCP clients and HTTP proxies wait, so the API returns 202 with a job
  id and the MCP server returns at once.
- **Prompt cache.** mlx-gen caches prompt embeddings so a repeated prompt skips the 11 GB text encoder. The tool
  points that cache at `models/prompt_embeds/` instead of `~/Library/Caches/mflux`.

### Benchmarks (M5 Max)

Measured on 2026-10-29 (8-bit package, 25 steps, 121 frames at 24 fps = 5.04 s):

| Run | Size | Time | Peak GPU memory |
|---|---|---|---|
| `wan-prepare --bench`, default memory settings | 832x480 | 726 s (12.1 min) | 32.7 GB |
| Through the API job queue, with this tool's memory settings | 832x480 | **688 s (11.5 min)** + 2 s model load | **23.0 GB** |

That is about 2.3 minutes of compute per second of video, roughly 10x LTX-2.5 on the same Mac. The memory settings
cost nothing in speed. mlx-gen's own M5 Max figure (25 steps, 101 frames at 832x480) is about 12 min, which matches.
In the test clips, subjects stay stable, but late frames can soften (a paper boat drifting away lost its shape in
the last second).

## Configuration

All variables live in the root `tools/.env` (see `.env.example`, section `video-gen / os`):

| Variable | Default | Purpose |
|---|---|---|
| `WAN_HF_REPO` / `WAN_HF_REVISION` | mlx-gen 8-bit package @ `6875952` | Model package |
| `WAN_MODEL_PATH` | empty | Use a local package folder instead of the HF download |
| `WAN_MODELS_DIR` | `models` | HF cache lives in `<this>/huggingface` |
| `WAN_OUTPUT_DIR` | `outputs` | Generated MP4s |
| `WAN_STEPS` | `25` | Default denoising steps (4–50) |
| `WAN_MAX_JOBS` | `100` | Finished jobs kept in memory |
| `WAN_PORT` / `WAN_MCP_PORT` | `8150` / `8151` | HTTP API / MCP streamable-HTTP port |
| `WAN_API_KEY` | empty | Optional bearer token for the HTTP API |
| `WAN_MAX_UPLOAD_MB` | `50` | Image-to-video upload limit |

The API and the MCP server each load their own model. Don't run jobs in both at once, or alongside `ltx`, on a
48 GB Mac.

## Also available from upstream

The `mlxgen` CLI in this venv exposes everything mlx-gen supports, including Wan A14B, video-to-video, VACE and the
image models: `uv run mlxgen --help`.

## Dependency notes

- mlx-gen installs as a path dependency. It ships a module named `mflux` (it is a fork of mflux), so it must stay in
  its own venv, separate from `image-gen/os/zimage`.
- Pillow is capped below 13: Pillow 13 does not import on this CPython.
- `pytest` is limited to `tests/` so it never collects upstream's test suite.

## Docs

[docs/API.md](docs/API.md) · [docs/MCP.md](docs/MCP.md) · [docs/AGENTS.md](docs/AGENTS.md) ·
[skills/wan/SKILL.md](skills/wan/SKILL.md)

## Tests

```bash
uv run pytest     # fake model; no weights or GPU needed
```
