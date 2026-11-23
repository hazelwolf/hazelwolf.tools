# HTTP API

```bash
uv run --directory <tool dir> imagegen-api      # http://127.0.0.1:8130, docs at /docs, OpenAPI at /openapi.json
```

Host and port come from `IMAGEGEN_API_HOST` (or `API_HOST`) and `IMAGEGEN_PORT`.

## Auth

None by default (binds to localhost). Set `IMAGEGEN_API_KEY` to require `Authorization: Bearer <key>` on every route.

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
 "weights_ready": true,
 "models": {
   "zimage": {"repo": "Tongyi-MAI/Z-Image-Turbo", "path": ".../models/z-image-turbo-q8", "weights_ready": true,
              "default_steps": 9, "img2img": true},
   "boogu": {"repo": "Boogu/Boogu-Image-0.1-Turbo", "path": ".../models/boogu-q8", "weights_ready": true,
             "default_steps": 8, "img2img": false}},
 "quantize": 8, "loaded": false, "loaded_model": null, "load_time_s": null, "idle_unload_s": 900.0,
 "device": "mlx-metal", "output_dir": ".../outputs"}
```

The top-level `weights_ready` is Z-Image's. `models.<name>.weights_ready: false` means that model's first use: its
weights are not downloaded yet, and the next `/generate` with it downloads (Z-Image ~33 GB, Boogu ~39 GB) and
quantizes them before answering, which can take 30-60 minutes. Run `uv run imagegen-prepare --model <name>` first to
avoid a request that long.

### `POST /generate`

| Field | Default | Notes |
|---|---|---|
| `prompt` | required | Detailed prompts work best; quoted words are rendered as text |
| `model` | `zimage` | `zimage`: people, photos, scenes, styles. `boogu`: text-heavy images (posters, menus, labels); ~60 s per image, no img2img |
| `width`, `height` | 1024 | 256–2048, rounded down to a multiple of 16 |
| `steps` | model's own | `zimage` 9, `boogu` 8 |
| `seed` | random | Returned per image |
| `count` | 1 | 1–8, seeds `seed`, `seed+1`, ... |
| `image_path` | – | Local init image for img2img |
| `image_strength` | 0.4 with `image_path` | 0–1 exclusive |
| `output_name` | auto | File stem; never overwrites (`-2`, `-3`, ... are added) |

```bash
curl -s localhost:8130/generate -H 'Content-Type: application/json' \
  -d '{"prompt": "a red fox in fresh snow, soft winter light", "seed": 42, "output_name": "fox"}'
```

```bash
curl -s localhost:8130/generate -H 'Content-Type: application/json' \
  -d '{"prompt": "a poster reading \"GRAND OPENING\" in bold letters, confetti", "model": "boogu", "output_name": "poster"}'
```

```json
{"model": "zimage",
 "images": [{"path": ".../outputs/fox.png", "name": "fox.png", "seed": 42, "generation_time_s": 16.0,
             "url": "http://127.0.0.1:8130/files/fox.png"}],
 "width": 1024, "height": 1024, "steps": 9, "quantize": 8, "load_time_s": 4.3}
```

### `POST /img2img` (multipart)

Fields: `prompt`, `image` (file: png/jpg/webp, up to `IMAGEGEN_MAX_UPLOAD_MB`), `image_strength=0.4`, `width`,
`height`, `steps`, `seed`, `output_name`. Same response as `/generate`. The upload is deleted after use. Always
Z-Image: Boogu has no img2img, and `/generate` with `model: "boogu"` and an `image_path` returns 400.

```bash
curl -s -F prompt='a variation with warmer evening light' -F image=@photo.png -F image_strength=0.4 localhost:8130/img2img
```

### `GET /files/{name}`

Returns a PNG from `outputs/`.

### `POST /unload`

Frees the model now. `{"unloaded": true}`.

## Postman

Import `postman/imagegen.postman_collection.json` and `postman/imagegen.postman_environment.json`, select the
environment, and run. Or import `http://127.0.0.1:8130/openapi.json` directly.
