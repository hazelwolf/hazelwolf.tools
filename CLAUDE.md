# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**`INSTRUCTIONS.md` is the authoritative rulebook** for this workspace (layout per category, uv, env vars, paths, git,
definition of done). Read it before adding or restructuring a tool; this file only summarizes and adds context.

## What this repo is

A monorepo of local AI generation tools for agents. Each tool lives at `<domain>/<category>/<tool>/`
(domains: `audio-gen`, `image-gen`, `video-gen`, `creative`, `media`; categories: `os` wraps a pinned upstream
submodule, `custom` is our own code, `third-party` wraps a paid API). Every tool is an independent uv project with its
own `.venv` and exposes the same capability three ways: an HTTP API, an MCP server and a `skills/<tool>/SKILL.md`.

Current tools: `image-gen/os/imagegen` (Z-Image-Turbo, plus Boogu Image Turbo for text-heavy images, via mflux/MLX),
`video-gen/os/ltx` (LTX-2.5 via ltx-2-mlx), `video-gen/os/wan` (Wan 2.2 via mlx-gen), `audio-gen/os/voicestudio`
(OmniVoice), `creative/custom/comfyflow` (runs saved ComfyUI workflows), `media/custom/localbox` (drop files into
tagged folders). `audio-gen/os/audiocraft` and
`image-gen/os/sensenova-u1` are partial scaffolds. `creative/os/creative-workflows` is ComfyUI itself (submodule) plus
workflow JSON, started with its `run.sh`. Target hardware is Apple Silicon (MLX/Metal).

`evals/image-gen` (CLI `imgeval`, its own uv project, no API/MCP/skill) compares the two imagegen models on a fixed
prompt set: one process per model, resumable runs, and a blind side-by-side `index.html` whose exported
`votes.json` is tallied with `imgeval tally`. See `evals/README.md`.

## Commands

Run everything per tool, from inside the tool folder (never a root venv, never bare `pip`):

```bash
cd image-gen/os/imagegen
uv sync                              # create/update the tool's .venv
uv run pytest                        # tests (fake models; no weights or GPU needed)
uv run pytest tests/test_api.py::test_health   # single test
uv run imagegen-api                    # HTTP API (FastAPI, /docs, /openapi.json, /health)
uv run imagegen-mcp                    # MCP server, stdio (--transport streamable-http for HTTP)
uv run imagegen-prepare                # os/ MLX tools: download + quantize weights ahead of first use
```

Entrypoints follow `<tool>-api`, `<tool>-mcp`, `<tool>-prepare` (see each `pyproject.toml` `[project.scripts]`);
`skills/hazelwolf/hw <tool> <cmd>` runs them from any directory. `hw install` links every tool's skill into
`~/.claude/skills` and registers every `<tool>-mcp` at Claude Code user scope; `hw test [tool...]` starts each MCP
server over stdio, lists its tools and calls its health tool. MCP launches use `uv run --frozen`: without it uv
re-fetches VoiceStudio's direct-URL spaCy wheel on every start (~50 s), past Claude Code's 30 s connect timeout.

Repo-wide (from the root):

```bash
uvx ruff check . && uvx ruff format .   # config in ruff.toml; **/upstream is force-excluded
pre-commit run --all-files              # gitleaks + ruff
git submodule update --init --recursive # if cloned without --recurse-submodules
creative/os/creative-workflows/run.sh   # start ComfyUI on 127.0.0.1:8188 (needed by comfyflow)
```

## Architecture

**Layering inside a tool.** `core.py` holds all logic; `api.py` (FastAPI) and `mcp_server.py` (FastMCP) are thin
wrappers that call `core` and never duplicate it. `core.ServiceError(message, status)` is the shared error type: the
API maps it to `{"error": ...}` with that status, the MCP layer re-raises it as `ValueError`. Blocking `core` calls are
pushed off the event loop with `anyio.to_thread.run_sync` so `/health` stays responsive. MCP tool docstrings are the
descriptions agents read, so they are written as prose (E501 is ignored in `mcp_server.py`).

**Config and import order.** The package `__init__.py` imports `config` first. `config` finds the workspace root by
walking up to the directory containing `INSTRUCTIONS.md`, loads the shared root `.env` (then an optional tool-local
`.env` override), and sets cache dirs like `HF_HOME` — this must happen before torch/mlx/huggingface import, which is why
it lives in `__init__.py` where the import sorter cannot reorder it. New env vars go into the root `.env.example` under
the tool's section, prefixed with the tool name.

**MLX model lifecycle (imagegen, ltx, wan).** One model per process, loaded lazily on first request (imagegen swaps
between Z-Image and Boogu per request's `model`, never holding both), freed by an idle reaper thread after
`<TOOL>_IDLE_UNLOAD_S`. MLX streams are bound to the thread that created them, so imagegen runs every
MLX call on a single-worker executor (`_on_mlx`); ltx serializes with a lock. Wan clips take ~10+ minutes, so wan uses
an in-memory job queue (`submit` / `get_job(wait_s)` / `list_jobs`) with one worker thread instead of a blocking call.
`prepare.py` downloads from Hugging Face (pinned revision) and saves a quantized copy under the tool's gitignored
`models/`; `health()` reports `weights_ready` only when the referenced weight files exist.

**Files, not bytes.** Inputs and outputs move as absolute local paths (outputs under the tool's gitignored `outputs/`;
the API also serves them at `/files/{name}`). Output names are reserved atomically with `O_CREAT|O_EXCL` so concurrent
processes never collide. Relative input paths are resolved against the cwd.

**Wrappers over other servers.** `voicestudio` launches the upstream VoiceStudio backend (`voicestudio-backend`) and its
`core` is an httpx client to it. `comfyflow` is an httpx client to a running ComfyUI: workflows are API-format JSON in
`creative/os/creative-workflows/workflows/api/`, and parameters are exposed by titling nodes `@name` (see
`creative/custom/comfyflow/docs/DESIGN.md`). `workflows.py` is pure and unit-tested without a server.

**Tests** monkeypatch `core._load_model` (or the HTTP backend) with fakes and point `config.OUTPUT_DIR` at `tmp_path`, so
they run without weights, GPU or network. Follow that pattern.

## Rules that are easy to miss

- Never edit anything under `upstream/` (submodules). Work around upstream issues in `src/`, via
  `[tool.uv] override-dependencies` / `constraint-dependencies`, or by bumping the pinned submodule commit deliberately
  (and updating the pin in the tool README).
- No machine-specific paths in anything committed; build absolute paths at run time
  (`"$(git rev-parse --show-toplevel)/<rel path>"`). Check with `git grep -nE '/Users/|/home/'`.
- When changing endpoints or MCP tools, update that tool's `docs/API.md`, `docs/MCP.md` and Postman collection in the
  same change.
- `custom/` tools keep a `CHANGELOG.md` and `docs/DESIGN.md`; new upstreams need a row in `docs/legal/LICENSE-NOTES.md`
  and `docs/ACKNOWLEDGEMENTS.md`.
- Skills are symlinked (not copied) into `.claude/skills/` and `.cursor/skills/`.
- Keep `docs/plan/KANBAN.md` current; mark a card Done only when verified, then move it to `archive.md`.
- Never bypass gitleaks with `--no-verify`; allowlist false positives in `.gitleaks.toml`.
- End each commit with the co-author trailer of the agent committing it (Claude Code or Cursor; see Git in
  `INSTRUCTIONS.md`), never another agent's.
