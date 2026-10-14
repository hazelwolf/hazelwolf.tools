# HTTP API

Start the upstream backend first, then the API:

```bash
cd audio-gen/os/voicestudio
uv run voicestudio-backend      # :3900
uv run voicestudio-api          # :8103 (OpenAPI at /openapi.json, docs at /docs)
```

Auth: none by default. If `VOICESTUDIO_API_KEY` is set, send `Authorization: Bearer <key>` on every request.

Errors: `{"error": "<message>"}` with the status code. 503 means the backend is not running or still starting;
404/422 come from the backend (unknown profile, bad audio).

## Endpoints

### `GET /health`

Wrapper status plus the backend's `/health`.

```bash
curl -s localhost:8103/health
```

```json
{"status": "ok", "backend_url": "http://127.0.0.1:3900", "output_dir": ".../outputs",
 "backend_ready": true, "backend": {"status": "ok", "device": "mps", "version": "0.5.6"}}
```

### `GET /voices`

Saved voice profiles.

```json
[{"id": "3f2a...", "name": "Ava", "kind": "clone", "language": "Auto", "created_at": "..."}]
```

### `GET /personalities`

Style presets (Narrator, Casual, News Anchor, ...) with the `instruct` text to pass to `/generate`.

### `POST /voices/clone` (multipart)

| Field | Required | Notes |
|---|---|---|
| `name` | yes | |
| `ref_audio` | yes | 5–30 s, one clean speaker; wav/mp3/flac/ogg/m4a/webm |
| `ref_text` | no | Transcript of the reference (improves quality) |
| `language` | no | ISO code or `Auto` |
| `instruct` | no | Default style |

```bash
curl -s -F name=Me -F ref_audio=@me.wav localhost:8103/voices/clone
# {"profile_id": "3f2a...", "name": "Me", "kind": "clone"}
```

### `DELETE /voices/{profile_id}`

```json
{"deleted": "3f2a..."}
```

### `POST /generate` (JSON)

| Field | Default | Notes |
|---|---|---|
| `text` | required | Long text is chunked and crossfaded by the backend |
| `profile_id` | default voice | From `/voices` |
| `language` | `Auto` | ISO 639 code |
| `instruct` | | e.g. `whisper`, `excited`, `narrator` |
| `speed` | `1.0` | 0.5–2.0 |
| `steps` | backend default | 8 draft, 16 balanced, 32 quality |
| `seed` | random | |
| `engine` | backend selection | Override the TTS engine |
| `output_name` | generated | File stem in `outputs/`; never overwrites (`-2`, `-3` ...) |

```bash
curl -s localhost:8103/generate -H 'Content-Type: application/json' \
  -d '{"text": "Hello from VoiceStudio.", "language": "en", "output_name": "hello"}'
```

```json
{"path": ".../outputs/hello.wav", "name": "hello.wav", "bytes": 96044, "audio_id": "a1b2",
 "duration_s": 1.9, "generation_time_s": 0.7, "url": "http://127.0.0.1:8103/files/hello.wav"}
```

The first call downloads the OmniVoice model (~2.3 GB) and can take several minutes.

### `POST /transcribe` (multipart)

| Field | Notes |
|---|---|
| `audio` | required |
| `language` | optional hint |
| `mode` | `fast` (default), `accurate` (word timings), `reference` |

```bash
curl -s -F audio=@clip.wav localhost:8103/transcribe
# {"text": "...", "language": "en", "duration": 4.2, ...}
```

### `GET /files/{name}`

Download a generated WAV from `outputs/`.

## Postman

Import `postman/voicestudio.postman_collection.json` and `postman/voicestudio.postman_environment.json`, and select the
**VoiceStudio** environment (`baseUrl`, `apiKey`). You can also import `http://127.0.0.1:8103/openapi.json`
directly. For the file fields in Clone and Transcribe, pick a local audio file.

The upstream backend has its own, larger API (dubbing, audiobooks, voice design, engines) with a reference at
`http://127.0.0.1:3900/docs`.
