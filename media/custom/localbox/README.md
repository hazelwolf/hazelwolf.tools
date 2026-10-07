# Localbox

A single page on the local network for dropping images and videos onto this machine. Each upload goes to a destination tag. The default tag is `comfy`, which writes into `/home/bhomit/Dev/genai/ComfyUI/input`.

No login. Anything that can open the page on the LAN can upload.

## Start

```bash
cd /home/bhomit/Dev/genai/tools/media/custom/localbox
uv sync
uv run localbox-api
```

Then open `http://<this-machine>:8120/` from a phone or another computer on the same network. The page lists those URLs when it can detect them.

Override bind address, port, destinations, and the size cap in `tools/.env` (`LOCALBOX_HOST`, `LOCALBOX_PORT`, `LOCALBOX_DESTINATIONS`, `LOCALBOX_MAX_MB`). See `tools/.env.example`.

## What it accepts

`png`, `jpg`, `jpeg`, `webp`, `gif`, `mp4`, `webm`, `mov`, `mkv`. The original filename is kept. If that name is already in the folder, the new file is `name-2.ext`, then `name-3.ext`. Nothing is overwritten.

## Layout

- `src/localbox_tool/core.py` — destination lookup and file writes
- `src/localbox_tool/api.py` — the page and HTTP API
- `src/localbox_tool/mcp_server.py` — MCP tools for agents
- `static/index.html` — the page

Docs: [docs/DESIGN.md](docs/DESIGN.md), [docs/API.md](docs/API.md), [docs/MCP.md](docs/MCP.md), [docs/AGENTS.md](docs/AGENTS.md).
