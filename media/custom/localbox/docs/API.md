# HTTP API

## Start

```bash
uv run --directory media/custom/localbox localbox-api
```

That listens on `LOCALBOX_HOST`:`LOCALBOX_PORT` (default `0.0.0.0:8120`). Interactive docs: `http://127.0.0.1:8120/docs`. OpenAPI: `http://127.0.0.1:8120/openapi.json`.

There is no auth.

Errors are JSON: `{"error": "message"}` with status 400 (bad type, empty file, unknown tag), 413 (over the size cap), or 500 (bad configuration).

## Postman

Import both files in `postman/`. Set `baseUrl` in the environment (default `http://127.0.0.1:8120`). The collection also imports from `/openapi.json`; the page route `GET /` is omitted from the schema because it returns HTML.

## GET /health

```bash
curl -s http://127.0.0.1:8120/health
```

```json
{
  "status": "ok",
  "host": "0.0.0.0",
  "port": 8120,
  "lan_urls": ["http://192.168.1.20:8120/"],
  "destinations": [
    {"tag": "comfy", "path": "/path/to/ComfyUI/input", "default": true}
  ],
  "max_mb": 2048,
  "allowed_suffixes": [".gif", ".jpeg", ".jpg", ".mkv", ".mov", ".mp4", ".png", ".webm", ".webp"]
}
```

`lan_urls` is empty when this machine has no non-loopback IPv4 address.

## GET /destinations

```bash
curl -s http://127.0.0.1:8120/destinations
```

```json
{
  "default": "comfy",
  "destinations": [
    {"tag": "comfy", "path": "/path/to/ComfyUI/input", "default": true}
  ]
}
```

## POST /upload

Multipart form: `destination` (tag, default `comfy`) and `file` (one image or video).

```bash
curl -s -F destination=comfy -F file=@./frame.png http://127.0.0.1:8120/upload
```

```json
{
  "tag": "comfy",
  "path": "/path/to/ComfyUI/input/frame.png",
  "name": "frame.png",
  "bytes": 12345
}
```

## GET /

The drop page. It loads `/health`, fills the destination selector (default tag selected), and uploads each dropped file to `/upload`.
