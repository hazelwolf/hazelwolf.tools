# HTTP API

```bash
uv run --directory <tool dir> zimage-api      # http://127.0.0.1:8130, docs at /docs, OpenAPI at /openapi.json
```

Host and port come from `ZIMAGE_API_HOST` (or `API_HOST`) and `ZIMAGE_PORT`.

## Auth

None by default (binds to localhost). Set `ZIMAGE_API_KEY` to require `Authorization: Bearer <key>` on every route.

## Errors

Validation errors from FastAPI return 422 with its usual `detail` body. Tool errors return
`{"error": "<message>"}` with 400 (bad input), 404 (missing file) or 500.

## Endpoints

### `GET /health`

```bash
curl -s localhost:8130/health
```

```json
{"status": "ok", "model": "Tongyi-MAI/Z-Image-Turbo", "model_path": ".../models/z-image-turbo-q8",
 "weights_ready": true, "quantize": 8, "loaded": false, "load_time_s": null, "idle_unload_s": 900.0,
 "device": "mlx-metal", "output_dir": ".../outputs"}
```

`weights_ready: false` means first use: the weights are not downloaded yet. The next `/generate` downloads (~33 GB)
and quantizes them before answering, which can take 30+ minutes. Run `uv run zimage-prepare` first to avoid a request
that long.

### `POST /generate`

| Field | Default | Notes |
|---|---|---|
| `prompt` | required | Detailed prompts work best; quoted words are rendered as text |
| `width`, `height` | 1024 | 256–2048, rounded down to a multiple of 16 |
| `steps` | 9 | Turbo is distilled for 8–9 |
| `seed` | random | Returned per image |
| `count` | 1 | 1–8, seeds `seed`, `seed+1`, ... |
| `image_path` | – | Local init image for img2img |
| `image_strength` | 0.4 with `image_path` | 0–1 exclusive |
| `output_name` | auto | File stem; never overwrites (`-2`, `-3`, ... are added) |

```bash
curl -s localhost:8130/generate -H 'Content-Type: application/json' \
  -d '{"prompt": "a red fox in fresh snow, soft winter light", "seed": 42, "output_name": "fox"}'
```

```json
{"images": [{"path": ".../outputs/fox.png", "name": "fox.png", "seed": 42, "generation_time_s": 16.0,
             "url": "http://127.0.0.1:8130/files/fox.png"}],
 "width": 1024, "height": 1024, "steps": 9, "quantize": 8, "load_time_s": 4.3}
```

### `POST /img2img` (multipart)

Fields: `prompt`, `image` (file: png/jpg/webp, up to `ZIMAGE_MAX_UPLOAD_MB`), `image_strength=0.4`, `width`,
`height`, `steps`, `seed`, `output_name`. Same response as `/generate`. The upload is deleted after use.

```bash
curl -s -F prompt='a variation with warmer evening light' -F image=@photo.png -F image_strength=0.4 localhost:8130/img2img
```

### `GET /files/{name}`

Returns a PNG from `outputs/`.

### `POST /unload`

Frees the model now. `{"unloaded": true}`.

## Postman

Import `postman/zimage.postman_collection.json` and `postman/zimage.postman_environment.json`, select the
environment, and run. Or import `http://127.0.0.1:8130/openapi.json` directly.
