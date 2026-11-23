# imagegen: Z-Image-Turbo + Boogu Image Turbo

Local text-to-image and img2img for agents with two models. It runs natively on Apple Silicon through
[mflux](https://github.com/filipstrand/mflux), an MLX implementation, and ships with an HTTP API, an MCP server and
the `/imagegen` skill.

- [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) (Tongyi Lab, 6B single-stream DiT, 9 steps) is
  the default: people, photos, scenes, art styles and img2img.
- [Boogu Image 0.1 Turbo](https://huggingface.co/Boogu/Boogu-Image-0.1-Turbo) (10B, 8 steps) is chosen per request
  with `model: "boogu"` for text-heavy images: posters, menus, labels, book covers, several lines of text.

The split comes from `evals/image-gen`, which compared both with FLUX.2 klein 4B and Qwen-Image 2.1 Turbo on the same
prompts. Boogu rendered long and multi-line text best but is ~3x slower, so Z-Image stays the default.

| | |
|---|---|
| Upstream | https://github.com/filipstrand/mflux (submodule at `upstream/`) |
| Pinned ref | `v.0.23.0` (`63cec2b005bbb255447e0b42521c5cc6d6d5121c`) |
| Code license | MIT (`upstream/LICENSE`) |
| Models | [`Tongyi-MAI/Z-Image-Turbo`](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) @ `f332072`, [`Boogu/Boogu-Image-0.1-Turbo`](https://huggingface.co/Boogu/Boogu-Image-0.1-Turbo) @ `53ad545` |
| Weights license | Apache-2.0 (both) |
| Commercial use | Yes |

## How it fits together

```
agent ── MCP (stdio) ─────────> imagegen-mcp ─┐
curl / Postman ── HTTP :8130 ──> imagegen-api ─┼─ core.py ─┬─ mflux ZImage     ── models/z-image-turbo-q8
                                               ┘           └─ mflux BooguImage ── models/boogu-q8
```

`core.py` holds one model per process. It loads on first use, runs one generation at a time, swaps in the other model
when a request asks for it (both at once would need ~41 GB), and frees the model after `IMAGEGEN_IDLE_UNLOAD_S` idle
seconds. Images move by file path: PNGs are written to `outputs/`, so nothing large enters
an agent's context.

## Setup

```bash
cd image-gen/os/imagegen
git submodule update --init upstream     # if the clone skipped submodules
uv sync                                  # Python 3.13, MLX 0.32
uv run imagegen-prepare                    # recommended: fetch Z-Image now instead of on first use
uv run imagegen-prepare --model boogu      # and Boogu, for text-heavy images (or --model all)
```

### Model weights (downloaded on first use)

The weights are **not in git**: `models/` is gitignored, here and at the workspace root. A fresh clone has none.

The first time each model is used, the tool fetches and prepares it itself, whether through the API, the MCP server
or `imagegen-prepare --model <name>`:

1. It downloads the repo at the pinned revision from Hugging Face into `models/.download/<model>/` (Z-Image ~33 GB,
   because the transformer ships in fp32; Boogu ~39 GB). No token is needed; both are public.
2. It quantizes the weights to `IMAGEGEN_QUANTIZE` bits and saves an MLX copy (`models/z-image-turbo-q8/`, 10 GB;
   `models/boogu-q8/`, 19 GB).
3. It deletes the original download, unless `IMAGEGEN_KEEP_DOWNLOAD=1` (or `imagegen-prepare --keep-download`) is set.

This takes as long as the download (often 30 minutes or more), and that first request waits for
it. MCP clients can time out on a call that long, so run `uv run imagegen-prepare` once before connecting an agent;
`check_health` reports `weights_ready`. A file lock makes a second process wait instead of downloading twice, and a
crash never leaves a half-written copy. Every later load reads the saved copy and needs no network.

For another bit width, run `imagegen-prepare --quantize 4` (or `0` for bf16), which downloads again if the original is
gone. Add `--bench` to time two generations.

The download goes to a plain folder, not the Hugging Face cache: huggingface_hub 1.x stores cached files in a shared
`hub/blobs/` folder, so deleting one model's cache folder would not free its space.

## Run

```bash
uv run imagegen-api                        # HTTP API on 127.0.0.1:8130 (docs at /docs)
uv run imagegen-mcp                        # MCP over stdio (agents launch this themselves)
```

## Optimization for this machine

This machine is an Apple M5 Max with 48 GB unified memory (40 GB GPU working set). The choices:

- **MLX instead of PyTorch MPS.** The diffusers pipeline runs on MPS, but mflux is written for MLX: Metal kernels,
  lazy evaluation, and `mx.compile` on the denoising step. It also runs the transformer in bf16 (mflux 0.21+), which
  upstream measured at ~30% faster than fp32 on an M5.
- **8-bit weights by default.** On unified memory, a 6B DiT is limited by memory bandwidth. Quantizing halves the bytes
  read per step and the memory held while loaded. Measured numbers are below.
- **Pre-quantized local copy.** Quantizing at every load re-reads 25 GB of fp32 weights. The first use does it once,
  so a cold load reads only the quantized copy.
- **float16 compute off.** mflux's `--compute-precision float16` helps M1/M2, which have slow bf16. On M4/M5 the gain is
  small or zero, so the tool leaves it off.
- **Memory hygiene.** The MLX buffer cache is capped (`IMAGEGEN_MLX_CACHE_LIMIT_GB=4`) and cleared after each request,
  and the model unloads after 15 idle minutes, so an idle MCP server does not hold GPU memory.

### Benchmarks (M5 Max, 1024x1024, 9 steps, warm model)

Measured with `imagegen-prepare --bench` on 2026-10-26. Time is per image and includes text encoding and VAE decode.

| Variant | Time per image | Peak GPU memory | Disk |
|---|---|---|---|
| bf16 compute, loaded from the original fp32 shards | 27–36 s | 31.4 GB | 33 GB |
| **8-bit (default)** | **16–18 s** | **11.0 GB** | **10 GB** |
| 4-bit | 18 s | 8.8 GB | 5.5 GB |

Boogu Image Turbo, 8-bit, 8 steps (measured in `evals/image-gen` and through `core`, 2026-11-12): **~58-60 s per
image** (up to ~96 s), **29.9 GB** peak, 19 GB on disk. Switching from Boogu back to Z-Image took 3.8 s to load.

8-bit runs about twice as fast as the unquantized weights, with about a third of the memory, and for the same seed
its image is nearly identical to bf16. 4-bit saves 2 GB more but is not faster here, and its image drifts from bf16
(a different pose and background for the same seed), so 8-bit is the default. Loading the saved 8-bit copy takes under a
second; MLX then reads the weights lazily during the first image.

## Models

| Variant | Disk | Use |
|---|---|---|
| `models/.download/<model>/` (original download) | ~33 / ~39 GB | Temporary; deleted after quantizing unless `IMAGEGEN_KEEP_DOWNLOAD=1` |
| `models/z-image-turbo-q8/` (default) | 10 GB | What the tool loads; made on first use |
| `models/boogu-q8/` | 19 GB | Loaded for `model: "boogu"`; made on its first use |
| `models/z-image-turbo-q4/` (optional) | 5.5 GB | `IMAGEGEN_QUANTIZE=4`, for Macs with less memory |

Weights are Apache-2.0. On another Mac, 16 GB of unified memory is enough for Z-Image with `IMAGEGEN_QUANTIZE=4`, and
24 GB+ with 8-bit. Boogu needs ~30 GB at 8-bit, so 48 GB+ is the practical minimum.
mflux also runs on Linux with CUDA through MLX's CUDA backend, but this tool is set up and tested only on macOS.

## Configuration

All variables live in the root `tools/.env` (see `.env.example`, section `image-gen / os`):

| Variable | Default | Purpose |
|---|---|---|
| `IMAGEGEN_QUANTIZE` | `8` | 3, 4, 5, 6, 8, or `bf16` |
| `IMAGEGEN_MODEL_PATH` | `models/z-image-turbo-q<bits>` | Local MLX copy; made on first use if missing |
| `IMAGEGEN_BOOGU_MODEL_PATH` | `models/boogu-q<bits>` | Boogu's local MLX copy |
| `IMAGEGEN_BOOGU_HF_REPO` / `IMAGEGEN_BOOGU_HF_REVISION` | `Boogu/Boogu-Image-0.1-Turbo` / `53ad545...` | Boogu source |
| `IMAGEGEN_KEEP_DOWNLOAD` | off | Keep the ~33 GB original download after quantizing |
| `IMAGEGEN_MODELS_DIR` | `models` | Quantized copies; downloads go to `<this>/.download` |
| `IMAGEGEN_OUTPUT_DIR` | `outputs` | Generated PNGs |
| `IMAGEGEN_IDLE_UNLOAD_S` | `900` | Free the model after this many idle seconds (0 = never) |
| `IMAGEGEN_MLX_CACHE_LIMIT_GB` | `4` | Cap on MLX's buffer cache |
| `IMAGEGEN_PORT` / `IMAGEGEN_MCP_PORT` | `8130` / `8131` | HTTP API / MCP streamable-HTTP port |
| `IMAGEGEN_API_KEY` | empty | Optional bearer token for the HTTP API |
| `IMAGEGEN_MAX_UPLOAD_MB` | `50` | img2img upload limit |

The API and the MCP server each load their own copy of the model when used. Run one of them at a time if memory is
tight.

## Dependency notes

- Upstream's lockfile does not apply to a path dependency, so `pyproject.toml` caps Pillow below 13: Pillow 13.0
  imports `numbers._IntegralLike`, which CPython 3.13 does not have.
- `pytest` is limited to `tests/` so it never collects upstream's own test suite.

## Docs

[docs/API.md](docs/API.md) · [docs/MCP.md](docs/MCP.md) · [docs/AGENTS.md](docs/AGENTS.md) ·
[skills/imagegen/SKILL.md](skills/imagegen/SKILL.md)

## Tests

```bash
uv run pytest     # fake model; no weights or GPU needed
```
