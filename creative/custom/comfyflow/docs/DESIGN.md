# Design

## Goal

Reuse workflows built in ComfyUI from agents and scripts. Design and debug a workflow in the ComfyUI UI, then run it by name with named parameters from the CLI, an HTTP API or MCP tools. No model code lives here: ComfyUI stays the engine and the only thing that touches the GPU.

## Architecture

```
cli.py ─┐
api.py ─┼─> core.py ──HTTP──> ComfyUI (127.0.0.1:8188)
mcp_server.py ─┘     └─> workflows.py (files, parameters; no network)
```

`core.py` calls ComfyUI's own HTTP API: `POST /prompt`, `GET /history/{id}`, `GET /queue`, `POST /interrupt`, `POST /upload/image`, `GET /system_stats`. `workflows.py` is pure and unit-tested without a server.

## Workflow format

A workflow is one ComfyUI **API-format** JSON file in `creative/os/creative-workflows/workflows/api/<name>.json` (override with `COMFYFLOW_WORKFLOWS_DIR`). The UI-format files in `workflows/` cannot be run directly, because they hold subgraphs and layout that only the frontend can flatten.

**Parameters come from node titles.** A node titled `@name` exposes its literal (not wired) inputs. One literal input gives the parameter `name`; several give `name.input` (for example `sampler.steps`). Types are taken from the current value. `LoadImage`, `LoadAudio` and `LoadVideo` inputs are `file` parameters: a local path is uploaded to ComfyUI's input folder. Any literal input can also be set with the raw form `node_id.input`.

Optional metadata sits under a top-level `_comfyflow` key (`description`, `params` docs) and is removed before submitting.

**Getting a workflow in.** Run it once in the ComfyUI UI, then `import` (CLI, API or MCP). The API-format graph is read from ComfyUI's run history, so no manual "Export (API)" step is needed, and common nodes (prompt, negative prompt, size, sampler, loaders, primitives) get `@` titles automatically. Rename nodes to `@something` in ComfyUI and import again with overwrite to expose more.

## Decisions

- **API-format only, titles instead of a schema file.** One file per workflow, and the parameter list is visible in the ComfyUI graph where the workflow is edited.
- **Import from history.** ComfyUI stores the exact API graph of every run. Reading it avoids a UI-to-API converter, which would have to re-implement subgraph flattening.
- **Seeds are randomized** when an exposed `seed` / `noise_seed` input is not supplied, like ComfyUI's "randomize". The seeds used are returned. `randomize_seed=false` keeps the saved value.
- **Blocking run by default**, with a timeout (`COMFYFLOW_TIMEOUT_S`, 3600). A timeout returns `status: timeout` and the job keeps running in ComfyUI; `wait=false` plus `get_job` suits long video jobs. No websocket progress for now.
- **Outputs are local paths.** ComfyUI and the caller share this machine, so files are returned as absolute paths under ComfyUI's `output/` instead of being streamed.
- **Local only.** Binds to `127.0.0.1`, no auth. File parameters read any local path the process can read (see `docs/legal/SECURITY.md`).
- ComfyUI must already be running. This tool does not start or stop it.

## Open questions

- Progress updates for long jobs (ComfyUI websocket) in the MCP server.
- Auto-starting ComfyUI when it is down.
- A converter for UI-format files, if importing from history turns out to be too indirect.
- Several ComfyUI instances or a remote one (`COMFYFLOW_COMFY_URL` already allows a URL; file paths assume the same machine).
