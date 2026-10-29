# HTTP API

```bash
uv run --directory <tool dir> ltx-api      # http://127.0.0.1:8140, docs at /docs, OpenAPI at /openapi.json
```

Host and port come from `LTX_API_HOST` (or `API_HOST`) and `LTX_PORT`.

## Auth

None by default (binds to localhost). Set `LTX_API_KEY` to require `Authorization: Bearer <key>` on every route.

## Errors

Validation errors from FastAPI return 422 with its usual `detail` body. Tool errors return `{"error": "<message>"}`
with 400 (bad input), 404 (missing file), 503 (model pack not downloadable: license not accepted or no `HF_TOKEN`)
or 500.

## Endpoints

### `GET /health`

```bash
curl -s localhost:8140/health
```

```json
{"status": "ok", "model": "dgrauet/ltx-2.5-mlx-q8", "weights_ready": true, "hf_token_set": true, "loaded": false,
 "low_ram": false, "idle_unload_s": 600.0, "output_dir": ".../outputs"}
```

`weights_ready: false` means first use. The next `/generate` downloads the gated pack (~45 GB) before answering, so
run `uv run ltx-prepare` first.

### `POST /generate`

| Field | Default | Notes |
|---|---|---|
| `prompt` | required | Subject and action, camera, lighting/style, then sound |
| `width`, `height` | 768, 512 | 256–1920, rounded down to a multiple of 64 |
| `duration_s` | 5 | 1–20 s, snapped to the model's frame grid; `null` lets the model choose |
| `fps` | 24 | 24, 25 or 30 |
| `seed` | random | Returned |
| `image_path` | – | Local image used as the first frame |
| `output_name` | auto | File stem; never overwrites (`-2`, `-3`, ... are added) |

```bash
curl -s localhost:8140/generate -H 'Content-Type: application/json' \
  -d '{"prompt": "Waves roll onto a quiet beach at golden hour, slow pan right, gulls calling", "duration_s": 4, "output_name": "beach"}'
```

```json
{"path": ".../outputs/beach.mp4", "name": "beach.mp4", "seed": 1234, "width": 768, "height": 512, "fps": 24.0,
 "frames": 97, "duration_s": 4.04, "audio": true, "generation_time_s": 58.0, "peak_memory_gb": 20.1,
 "url": "http://127.0.0.1:8140/files/beach.mp4"}
```

The request blocks until the clip is done (minutes); give your HTTP client a long timeout.

### `POST /img2video` (multipart)

Fields: `prompt`, `image` (file: png/jpg/webp, up to `LTX_MAX_UPLOAD_MB`), `width`, `height`, `duration_s=5`,
`fps=24`, `seed`, `output_name`. Same response as `/generate`. The upload is deleted after use.

```bash
curl -s -F prompt='the camera slowly pushes in as she smiles' -F image=@still.png -F duration_s=4 localhost:8140/img2video
```

### `GET /files/{name}`

Returns an MP4 from `outputs/`.

### `POST /unload`

Frees the pipeline now. `{"unloaded": true}`.

## Postman

Import `postman/ltx.postman_collection.json` and `postman/ltx.postman_environment.json`, select the environment, and
run. Or import `http://127.0.0.1:8140/openapi.json` directly.
