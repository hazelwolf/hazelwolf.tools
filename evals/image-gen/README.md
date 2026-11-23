# Image-gen eval

Compares the two models `image-gen/os/imagegen` serves, Z-Image-Turbo and Boogu Image Turbo, on a fixed prompt set,
then lets a person pick winners on a blind side-by-side page. Speed and memory are measured on the same run. Use it
to check the routing rule (Z-Image for people and general images, Boogu for text-heavy ones) and to try new
candidates.

Everything runs locally through mflux (MLX, Apple Silicon). The eval reuses the mflux submodule pinned by
`image-gen/os/imagegen/upstream`, so the baseline is the exact code imagegen serves and no second copy of mflux exists.

## Models

| Key | Model | Steps | Download | Weights license |
|---|---|---|---|---|
| `zimage` | [Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) (6B) | 9 | reuses imagegen's copy | Apache-2.0 |
| `boogu` | [Boogu/Boogu-Image-0.1-Turbo](https://huggingface.co/Boogu/Boogu-Image-0.1-Turbo) (10B) | 8 | reuses imagegen's copy | Apache-2.0 |

Each model runs at its own recommended step count (Boogu uses 8 because mflux recommends 8 at 1024 px). Everything
else is the same: prompts, seeds, size, 8-bit quantization and the MLX cache limit. Revisions are pinned in
`src/imgeval/models.py`.

### First comparison (smoke run, 2026-11-12)

Four models, 5 prompts (one per category), 1 seed, 1024x1024, 8-bit, on an M5 Max:

| Model | s / image | Peak GB | Notes | Kept? |
|---|---|---|---|---|
| Z-Image-Turbo | ~19 | 11.0 | Counting right; strong people and photos | **Yes**: people and general images |
| Boogu Image Turbo | ~60 | 29.9 | Counting right; most photographic; best long text | **Yes**: text-heavy images |
| FLUX.2 klein 4B | ~5 | 12.6 | Fastest; miscounted (2 apples + 1 pear for 3 + 2) | No |
| Qwen-Image 2.1 Turbo | ~22-39 | 36.0 | Miscounted; grey fox for a red one; non-commercial license | No |

Adding a model back means adding a `ModelSpec` in `src/imgeval/models.py`; the mflux classes for both are in the
pinned submodule (`Flux2Klein`, `QwenImage21`).

## Setup

```bash
cd evals/image-gen
uv sync
uv run imgeval list          # what is downloaded
uv run imgeval prepare       # only needed if imagegen has not prepared both models (imagegen-prepare --model all)
```

`prepare` (or the first run) downloads each repo at its pinned revision, saves an 8-bit MLX copy under `models/`
(gitignored) and deletes the original download unless `IMGEVAL_KEEP_DOWNLOAD=1`. If imagegen already has
`models/z-image-turbo-q8` or `models/boogu-q8`, the eval uses those.

Memory: each model runs in its own process, so only one is loaded at a time. Boogu peaks at ~30 GB at 8-bit, so a
48 GB Mac is enough as long as no other large model (LTX, Wan, ComfyUI) is loaded at the same time.

## Run

```bash
uv run imgeval run --name smoke --limit 1 --seeds 1   # 5 prompts, one per category: quick check
uv run imgeval run --name full                        # 40 prompts x 2 seeds x 2 models = 160 images, ~2 h
uv run imgeval run --name full --category text        # only the text-heavy prompts
```

Results go to `outputs/<name>/` (gitignored):

```
run.json                 prompts, seeds, size and models of the run
images/<model>/<prompt>-s<seed>.png
results/<model>.jsonl    seconds per image
results/<model>.meta.json  load time, peak memory, weights used
index.html               blind review page
```

Runs resume: re-running the same `--name` skips images that already exist and keeps the original prompts, seeds and
size. If a model fails, the others still run, and the command exits non-zero with the failed model's name.

## Review

Open `outputs/<name>/index.html` in a browser. Each page shows one prompt and seed, with every model's image under
a letter (A, B) in a shuffled order. Click the best image or press `1`/`2`; `0` = tie, `X` = all bad, arrow keys
move. Votes are saved in the browser. **Reveal results** shows wins per category, plus speed, memory and
licenses.

**Export votes.json**, put it in the run folder and tally from the terminal (or let an agent read it):

```bash
uv run imgeval tally full                     # reads outputs/full/votes.json
uv run imgeval tally full ~/Downloads/votes.json
uv run imgeval report full                    # rebuild the page (same shuffles)
```

## Prompt set

`prompts.toml`, 40 prompts in five categories of 8:

| Category | Tests |
|---|---|
| `photo` | Photorealism: light, materials, texture |
| `text` | Text inside the image, English and one Chinese sign |
| `composition` | Counting, placement, binding colours to objects |
| `style` | Watercolour, vector, ukiyo-e, pixel art, line art, anime |
| `people` | Faces, hands, poses, groups |

Each prompt has a `check` line telling the reviewer what to look at. Ids are stable; add prompts with new ids
instead of rewording old ones, so past votes keep their meaning.

## Settings

All optional, in the root `.env` (see `.env.example`, section "evals"):

| Variable | Default | Meaning |
|---|---|---|
| `IMGEVAL_QUANTIZE` | `8` | Bit width for every model (`bf16` for none) |
| `IMGEVAL_MODELS_DIR` | `evals/image-gen/models` | Quantized copies and the HF cache |
| `IMGEVAL_OUTPUT_DIR` | `evals/image-gen/outputs` | Run folders |
| `IMGEVAL_PROMPTS` | `evals/image-gen/prompts.toml` | Prompt set |
| `IMGEVAL_KEEP_DOWNLOAD` | off | Keep the original HF downloads |
| `IMGEVAL_MLX_CACHE_LIMIT_GB` | `4` | MLX buffer cache cap |

## Tests

```bash
uv run pytest     # fake models; no weights, GPU or network
```
