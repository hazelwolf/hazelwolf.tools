# HTTP API

```bash
uv run --directory <tool dir> wan-api      # http://127.0.0.1:8150, docs at /docs, OpenAPI at /openapi.json
```

Host and port come from `WAN_API_HOST` (or `API_HOST`) and `WAN_PORT`.

## Auth

None by default (binds to localhost). Set `WAN_API_KEY` to require `Authorization: Bearer <key>` on every route.

## Errors

Validation errors from FastAPI return 422 with its usual `detail` body. Tool errors return `{"error": "<message>"}`
with 400 (bad input), 404 (missing file or unknown job) or 500. A job that fails while running reports
`status: "failed"` and `error` on `GET /jobs/{job_id}`.

## Jobs

A clip takes about 12 minutes (832x480, 5 s, 25 steps on an M5 Max), so `/generate` and `/img2video` queue a job
and answer **202** at once. Poll `GET /jobs/{job_id}`, optionally holding the request with `?wait_s=N` (max 300) so
it answers as soon as the job finishes. One worker runs jobs in order. Jobs live in memory; restarting the server
clears them (finished MP4s stay in `outputs/`).

## Endpoints

### `GET /health`

```json
{"status": "ok", "model": "AbstractFramework/wan2.2-ti2v-5b-diffusers-8bit", "weights_ready": true, "active_jobs": 0,
 "default_steps": 25, "max_size": "1024x576 (width x height area)", "output_dir": ".../outputs"}
```

### `POST /generate` → 202

| Field | Default | Notes |
|---|---|---|
| `prompt` | required | Subject and action, camera, lighting and style |
| `width`, `height` | 832, 480 | 256–1024, rounded down to a multiple of 32; width x height at most 1024x576 (memory) |
| `duration_s` | 5 | 0.5–5.04 s at 24 fps (snapped to 4k+1 frames, max 121) |
| `steps` | 25 (`WAN_STEPS`) | 4–50; 50 is Wan's reference quality |
| `seed` | random | Returned in the result |
| `image_path` | – | Local image used as the first frame; output follows its aspect ratio |
| `negative_prompt` | Wan's default | What to avoid |
| `output_name` | auto | File stem; never overwrites (`-2`, `-3`, ... are added) |

```bash
curl -s localhost:8150/generate -H 'Content-Type: application/json' \
  -d '{"prompt": "A paper boat drifts down a rain-filled gutter, low tracking shot", "duration_s": 4, "output_name": "boat"}'
```

```json
{"job_id": "a1b2c3d4e5f6", "status": "queued", "phase": "queued", "step": 0, "total_steps": 25,
 "created_at": 1793000000.0, "prompt": "A paper boat drifts...", "result": null, "error": null, "queue_position": 0}
```

### `POST /img2video` (multipart) → 202

Fields: `prompt`, `image` (file: png/jpg/webp, up to `WAN_MAX_UPLOAD_MB`), `width`, `height`, `duration_s`, `steps`,
`seed`, `negative_prompt`, `output_name`. Same response as `/generate`. The upload is deleted when the job ends.

```bash
curl -s -F prompt='she turns toward the window and smiles' -F image=@still.png -F duration_s=4 localhost:8150/img2video
```

### `GET /jobs/{job_id}?wait_s=0`

```bash
curl -s "localhost:8150/jobs/a1b2c3d4e5f6?wait_s=60"
```

While running: `{"status": "running", "phase": "denoise", "step": 12, "total_steps": 25, ...}`. When done:

```json
{"job_id": "a1b2c3d4e5f6", "status": "done", "phase": "done", "step": 25, "total_steps": 25,
 "result": {"path": ".../outputs/boat.mp4", "name": "boat.mp4", "seed": 1234, "width": 832, "height": 480, "fps": 24,
            "frames": 97, "duration_s": 4.04, "steps": 25, "audio": false, "generation_time_s": 560.0,
            "load_time_s": 2.2, "peak_memory_gb": 23.0, "url": "http://127.0.0.1:8150/files/boat.mp4"},
 "error": null}
```

### `GET /jobs`

All jobs in this process, newest first.

### `GET /files/{name}`

Returns an MP4 from `outputs/`.

## Postman

Import `postman/wan.postman_collection.json` and `postman/wan.postman_environment.json`, select the environment, run
"Generate video", then "Get job" until `status` is `done`, then "Download video". Or import
`http://127.0.0.1:8150/openapi.json` directly.
