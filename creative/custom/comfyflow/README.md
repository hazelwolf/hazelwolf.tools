# comfyflow

Thin wrapper that runs [ComfyUI](../../os/creative-workflows/README.md) workflows by name with named parameters, from a CLI, an HTTP API or MCP tools. Design a workflow in the ComfyUI UI, run it once, import it, and agents can reuse it. ComfyUI does all the work; this tool holds no model code.

Our own code, Apache 2.0 (see the repo `LICENSE`). Design notes: `docs/DESIGN.md`.

## Setup and run

ComfyUI first (from the repo root):

```bash
creative/os/creative-workflows/run.sh
```

Then, from the repo root:

```bash
uv sync --directory creative/custom/comfyflow
uv run --directory creative/custom/comfyflow comfyflow list
uv run --directory creative/custom/comfyflow comfyflow describe z_image_turbo
uv run --directory creative/custom/comfyflow comfyflow run z_image_turbo prompt="a red fox in snow" size.width=832 size.height=1216
```

Servers: `comfyflow-api` (`127.0.0.1:8130`) and `comfyflow-mcp` (stdio). Agent configs: `docs/AGENTS.md`.

## Workflows

Files in `creative/os/creative-workflows/workflows/api/` (ComfyUI API format):

| Name | What it does | Typical time on the 12 GB GPU |
|---|---|---|
| `z_image_turbo` | Text to image, Z-Image Turbo bf16, 8 steps | about 12 s at 1024x1024 |
| `video_ltx2_3_id_lora` | Talking-person video with audio from a reference image, voice and prompt, LTX-2.3 22B fp8 | about 1-1.5 min for 5 s at 832x480 |

Add your own: run it once in the ComfyUI UI, then `comfyflow import <name> --description "..."`. Nodes titled `@name` become parameters; the import titles common nodes for you.

## Configuration (root `.env`)

| Variable | Default |
|---|---|
| `COMFYFLOW_COMFY_URL` | `http://127.0.0.1:8188` |
| `COMFYFLOW_COMFY_DIR` | `creative/os/creative-workflows` (where `output/` lives) |
| `COMFYFLOW_WORKFLOWS_DIR` | `<COMFY_DIR>/workflows/api` |
| `COMFYFLOW_HOST` / `COMFYFLOW_PORT` | `127.0.0.1` / `8130` (MCP over HTTP uses port + 1) |
| `COMFYFLOW_TIMEOUT_S` | `3600` |

## Test

```bash
uv run --directory creative/custom/comfyflow pytest
```

Unit tests use a fake ComfyUI; they need no GPU.
