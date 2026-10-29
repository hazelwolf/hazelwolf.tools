# HTTP API

Start (default `127.0.0.1:8130`, docs at `/docs`):

```bash
uv run --directory creative/custom/comfyflow comfyflow-api
```

ComfyUI must be running (`creative/os/creative-workflows/run.sh`). Errors are `{"error": "..."}` with status 400 (bad workflow, parameter or ComfyUI validation), 404 (unknown workflow or job) or 503 (ComfyUI unreachable).

| Method and path | Purpose |
|---|---|
| `GET /health` | ComfyUI version, GPU, free VRAM, workflow count |
| `GET /v1/workflows` | Workflows with description and parameter names |
| `GET /v1/workflows/{name}` | Parameters (name, type, default, description) and output nodes |
| `POST /v1/workflows/{name}/run` | Run. Body: `params`, `wait` (true), `timeout_s`, `randomize_seed` (true) |
| `POST /v1/workflows/import` | Save a run from ComfyUI as a workflow. Body: `name`, `prompt_id`, `description`, `overwrite` |
| `GET /v1/jobs/{prompt_id}` | `queued`, `running`, `success` or `error`, with files once finished |
| `POST /v1/jobs/{prompt_id}/cancel` | Cancel or interrupt |

## Examples

```bash
curl -s localhost:8130/v1/workflows/z_image_turbo

curl -s -X POST localhost:8130/v1/workflows/z_image_turbo/run \
  -H 'content-type: application/json' \
  -d '{"params": {"prompt": "a red fox in snow", "size.width": 832, "size.height": 1216}}'
```

Result:

```json
{"prompt_id": "…", "status": "success", "seconds": 12.3,
 "files": [{"kind": "image", "path": "/abs/path/output/z-image-turbo_00004_.png", "exists": true}],
 "seeds": {"sampler.seed": 155134342438134}}
```

File parameters (`image`, `audio`) take a local path; it is uploaded to ComfyUI first. For long jobs send `"wait": false` and poll `/v1/jobs/{prompt_id}`.

Import a workflow after running it once in the ComfyUI UI:

```bash
curl -s -X POST localhost:8130/v1/workflows/import -H 'content-type: application/json' \
  -d '{"name": "my_flow", "description": "what it does"}'
```

Postman: `postman/comfyflow.postman_collection.json` with `postman/comfyflow.postman_environment.json`.
