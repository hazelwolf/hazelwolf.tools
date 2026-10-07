# Design

## Goal

Give a phone or another computer on the LAN one page to drop images and videos onto this machine, and route each file to a named folder. The first folder is ComfyUI’s input directory.

## Architecture

The browser talks only to FastAPI. FastAPI and the MCP server both call `core`. The page is a static file with no build step.

```
browser -- POST /upload (tag + file) --> api.py --> core.save_stream --> destination folder
agent   -- save_file(path, tag)      --> mcp     --> core.save_path   --> destination folder
```

Destination tags come from `LOCALBOX_DESTINATIONS` (`tag=/absolute/path`, comma-separated). When that variable is unset, the only tag is `comfy` → `../ComfyUI/input`.

## Decisions

- Open on the LAN (`0.0.0.0`), no token. Chosen so a phone can upload without pairing. The page is only as private as the network.
- One file per `POST /upload`. The page uploads a dropped batch one file at a time so each file can show its own progress.
- Filenames are the basename only, with a lowercased suffix. `../../x.PNG` becomes `x.png` inside the destination. Existing names get `-2`, `-3`, … and are never replaced.
- Type check is the suffix, not file contents. Allowed: png, jpg, jpeg, webp, gif, mp4, webm, mov, mkv.
- Size cap defaults to 2048 MB and is enforced while the bytes are written. A file that crosses the cap is deleted.
- Empty files are rejected.
- MCP copies a path that already exists on this machine. It does not accept raw upload bytes.

## Open questions

- A shared PIN, if the LAN should not be fully open.
- Extra tags beyond `comfy` (add them in `LOCALBOX_DESTINATIONS`; no code change).
- Browsing or deleting files already in a destination. Not part of this tool.
