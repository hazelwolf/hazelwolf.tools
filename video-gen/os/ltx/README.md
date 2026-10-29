# LTX-2.5 video

Local text-to-video and image-to-video, with synchronized stereo audio, for agents. It runs
[LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) (Lightricks, 22B, August 2026) natively on Apple Silicon through
[ltx-2-mlx](https://github.com/dgrauet/ltx-2-mlx), a pure MLX port, and ships with an HTTP API, an MCP server and the
`/ltx` skill.

| | |
|---|---|
| Upstream | https://github.com/dgrauet/ltx-2-mlx (submodule at `upstream/`) |
| Pinned ref | `v0.18.0` (`b82b97e3d000e01361f8cfcb745244b15b89a521`) |
| Code license | MIT (`upstream/LICENSE`) |
| Model | [`dgrauet/ltx-2.5-mlx-q8`](https://huggingface.co/dgrauet/ltx-2.5-mlx-q8) @ `746ca9a` (gated), the 8-bit MLX conversion of `Lightricks/LTX-2.5` |
| Weights license | LTX-2.x Community License. See [LICENSE-NOTES.md](LICENSE-NOTES.md) |
| Commercial use | Yes under $10M annual revenue; above that, a paid license from Lightricks |

## How it fits together

```
agent ── MCP (stdio) ──> ltx-mcp ─┐
curl / Postman ── HTTP :8140 ──> ltx-api ─┼─ core.py ── ltx-2-mlx DistilledPipeline (MLX, Metal GPU) ── models/huggingface
                                          ┘
```

`core.py` keeps one pipeline per process and runs one clip at a time. MP4s (H.264 video + AAC stereo audio) are
written to `outputs/`, so nothing large enters an agent's context.

## Setup

```bash
cd video-gen/os/ltx
git submodule update --init upstream     # if the clone skipped submodules
uv sync                                  # Python 3.11, MLX 0.32.2
brew install ffmpeg                      # video encoding (already installed on this machine)
```

### Model weights (gated, downloaded on first use)

The weights are **not in git**: `models/` is gitignored. The pack is gated on Hugging Face, so once per account:

1. Open https://huggingface.co/dgrauet/ltx-2.5-mlx-q8 while signed in, and accept the LTX-2.x Community License.
2. Create a read token at https://huggingface.co/settings/tokens and set `HF_TOKEN=` in `tools/.env` (or run
   `hf auth login`).
3. Download now rather than on the first request:

   ```bash
   uv run ltx-prepare
   ```

The tool fetches only what the distilled pipeline needs, about 45 GB. That's the distilled transformer, the Gemma-4
text encoder, the VAEs, the vocoder and the upscalers. It skips the 21 GB dev transformer and the 9 GB distilled LoRA
in the same repo. Interrupted downloads resume. `check_health` reports `weights_ready` and `hf_token_set`; a request
made without the license or token fails with a 503 that says what to do.

## Run

```bash
uv run ltx-api                           # HTTP API on 127.0.0.1:8140 (docs at /docs)
uv run ltx-mcp                           # MCP over stdio (agents launch this themselves)
```

## Choices for this machine

This machine is an Apple M5 Max with 48 GB unified memory (40 GB GPU working set).

- **Why LTX-2.5 via ltx-2-mlx.** LTX-2.5 is Lightricks' newest open model and makes audio together with video.
  Lightricks' own code targets CUDA. ltx-2-mlx is a pure MLX port, updated weekly, whose pipelines mirror upstream
  and whose maturity is documented per pipeline. The diffusers/PyTorch route on MPS has no audio path and runs far
  slower on a 22B model.
- **8-bit pack.** The bf16 pack (120 GB repo, ~44 GB transformer) does not fit the working set. 8-bit (~21 GB
  transformer) fits without streaming. 4-bit fits 16 GB Macs but loses detail.
- **Distilled pipeline.** `DistilledPipeline` is in upstream's Stable tier. It renders at half resolution in 8 steps,
  upscales 2x, then refines in 3 steps, with no CFG, so it is the fastest mode by a wide margin. The dev + CFG
  pipelines (`--two-stage`, `--two-stages-hq`) are higher quality but several times slower and need the extra 30 GB.
- **Memory.** Upstream frees the Gemma text encoder before loading the transformer and frees the transformer before
  the decoders (`low_memory=True`), so peak memory stays near the transformer size. `LTX_LOW_RAM=1` streams
  transformer blocks from disk for Macs under 32 GB. The pipeline unloads after 10 idle minutes.

### Benchmarks (M5 Max, 768x512, 5 s at 24 fps)

Measured with `ltx-prepare --bench` on 2026-10-29 (8-bit pack, distilled pipeline, default settings):

| Clip | Wall time | Peak GPU memory | Output |
|---|---|---|---|
| 768x512, 121 frames (5.04 s), first clip in the process | 76 s | 20.1 GB | H.264 + AAC 48 kHz stereo, ~1 MB |
| same, second clip | 70 s | 20.1 GB | same |

That is about 14 s of compute per second of video at 768x512. Time includes loading the text encoder and transformer
for each clip (upstream frees them in between to keep peak memory low). Peak memory is half the GPU working set, so
HD and longer clips have headroom. They have not been timed yet, and they cost more than linearly, because attention
grows with the square of the token count.

The first-use download took about 90 minutes at ~7 MB/s for 42 GB on disk.

## Configuration

All variables live in the root `tools/.env` (see `.env.example`, section `video-gen / os`):

| Variable | Default | Purpose |
|---|---|---|
| `HF_TOKEN` | empty | Hugging Face read token; needed once for the gated download |
| `LTX_HF_REPO` | `dgrauet/ltx-2.5-mlx-q8` | Model pack (`-q4` for 16–32 GB Macs) |
| `LTX_HF_REVISION` | `746ca9a…` | Pinned pack revision |
| `LTX_MODEL_PATH` | empty | Use a local pack folder instead of the HF download |
| `LTX_MODELS_DIR` | `models` | HF cache lives in `<this>/huggingface` |
| `LTX_OUTPUT_DIR` | `outputs` | Generated MP4s |
| `LTX_LOW_RAM` | off | Stream transformer blocks from disk (Macs under 32 GB) |
| `LTX_IDLE_UNLOAD_S` | `600` | Free the pipeline after this many idle seconds (0 = never) |
| `LTX_PORT` / `LTX_MCP_PORT` | `8140` / `8141` | HTTP API / MCP streamable-HTTP port |
| `LTX_API_KEY` | empty | Optional bearer token for the HTTP API |
| `LTX_MAX_UPLOAD_MB` | `50` | Image-to-video upload limit |

The API and the MCP server each build their own pipeline when used. Don't run clips in both at once on a 48 GB Mac.

## Also available from upstream

The `ltx-2-mlx` CLI in this venv exposes everything the port supports. That includes audio-to-video, retake and
extend, IC-LoRA, HDR, and the dev + CFG pipelines (those need the full pack, so set `LTX_HF_REPO` and re-download
without the ignore list):

```bash
uv run ltx-2-mlx --help
```

## Dependency notes

- Upstream is a uv workspace. This tool depends on its `ltx-core-mlx` and `ltx-pipelines-mlx` packages as path
  dependencies and mirrors its lockfile pins for MLX and Pillow (Pillow 13 does not import on this CPython).
- `pytest` is limited to `tests/` so it never collects upstream's own test suite.

## Docs

[docs/API.md](docs/API.md) · [docs/MCP.md](docs/MCP.md) · [docs/AGENTS.md](docs/AGENTS.md) ·
[skills/ltx/SKILL.md](skills/ltx/SKILL.md)

## Tests

```bash
uv run pytest     # fake pipeline; no weights or GPU needed
```
