---
name: localbox
description: >-
  Save images and videos into a tagged folder on this machine. Use when the user
  wants to drop, upload, or copy a png, jpg, webp, gif, mp4, webm, mov, or mkv
  into ComfyUI input (tag comfy) or another configured localbox destination.
---

# Localbox

Use this when a local image or video should land in a destination folder. The default tag `comfy` writes to `creative/os/creative-workflows/input`.

Prefer the MCP tools. Fall back to the HTTP API if MCP is not connected.

## MCP

1. `list_destinations` — confirm the tag and folder.
2. `save_file` — copy a file that already exists on this machine.

```json
{"source_path": "/absolute/path/to/frame.png", "destination": "comfy"}
```

Expected result:

```json
{"tag": "comfy", "path": "/path/to/ComfyUI/input/frame.png", "name": "frame.png", "bytes": 12345}
```

If the name already exists, the saved name is `frame-2.png`, then `frame-3.png`.

## HTTP

Start the page (open on the LAN, no auth):

```bash
uv run --directory media/custom/localbox localbox-api
```

Open `http://<lan-ip>:8120/` to drag files in, or:

```bash
curl -s -F destination=comfy -F file=@./frame.png http://127.0.0.1:8120/upload
```

Details: `docs/API.md` and `docs/MCP.md`.
