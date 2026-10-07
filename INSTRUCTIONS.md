# Workspace Instructions

This workspace holds tools that AI agents (Claude Code, Cursor, OpenCode, Pi) use. When asked to set up a repo/tool here, follow every rule below.

## Workspace structure

Tools are grouped by domain, then by category:

```
tools/
├── INSTRUCTIONS.md
├── LICENSE / NOTICE      # Apache 2.0 (our code only)
├── docs/ACKNOWLEDGEMENTS.md  # thanks to upstream projects and the OSS community
├── docs/legal/           # DISCLAIMER, SECURITY, LICENSE-NOTES
├── .gitmodules           # OS upstream repos (submodules)
├── .env.example          # shared env template; copy to .env (gitignored)
├── audio-gen/            # audio generation (TTS, music, SFX, voice cloning, ...)
│   ├── os/               # open-source tools
│   ├── custom/           # built manually, together with the user
│   └── third-party/      # paid third-party APIs and systems
└── video-gen/            # video generation (text/image-to-video, editing, ...)
    ├── os/
    ├── custom/
    └── third-party/
```

A tool is a folder directly under `<domain>/<category>/`, e.g. `audio-gen/os/kokoro/`. New domains follow the same `os/ custom/ third-party/` split. Rules 1-3 below apply to every tool in every category; the category only changes what the tool folder contains and how it is sourced.

## Layout per category

Common to all categories (the tool-level standard):

```
<domain>/<category>/<tool>/
├── pyproject.toml          # uv-managed (Python tools)
├── uv.lock
├── .venv/                  # per-tool venv, created by `uv sync`
├── src/<tool_pkg>/
│   ├── core.py             # logic shared by API and MCP
│   ├── api.py              # HTTP API (FastAPI)
│   └── mcp_server.py       # MCP server (FastMCP / official mcp SDK)
├── postman/
│   ├── <tool>.postman_collection.json
│   └── <tool>.postman_environment.json
├── docs/
│   ├── API.md              # endpoints, request/response, curl + Postman usage
│   ├── MCP.md              # MCP tools/resources, how agents invoke them
│   └── AGENTS.md           # per-agent config snippets (Claude, Cursor, OpenCode, Pi)
├── skills/<tool>/SKILL.md  # user-invocable skill (rule 3)
├── tests/
└── README.md
```

### `os/` - open source
Wraps an existing open-source project. Do not edit upstream code.
- `upstream/` - the OSS project as a **git submodule** (never a plain copy, never edit it). Add with `git submodule add <repo-url> <domain>/os/<tool>/upstream`, then `git -C <that path> checkout <commit-or-tag>` and commit, so the pin is recorded in the superproject. Record repo URL, pinned commit/tag and license in the tool's `README.md`. Every OSS repo that is cloned or used here must be a submodule so a fresh clone fetches it.
- Install the upstream as a uv path dependency (`[tool.uv.sources] x = { path = "upstream", editable = true }`); if its pins conflict with the hardware/Python, use `[tool.uv] override-dependencies` rather than patching upstream, and wrap incompatibilities in our `src/` code.
- `src/<tool_pkg>/core.py` is a thin adapter over upstream; `api.py` and `mcp_server.py` wrap `core.py`.
- `models/` (gitignored) - downloaded weights. Document download steps, sizes and GPU/VRAM requirements in `README.md`; run the system-profiler skill to check the model fits.
- Add `LICENSE-NOTES.md` if the license restricts commercial use.

### `custom/` - built manually (by the user and Claude)
Our own code; there is no upstream.
- Full ownership of `src/`; add `docs/DESIGN.md` (goal, architecture, decisions, open questions) before substantial code.
- Pair-built: keep `tests/` meaningful and a `CHANGELOG.md` of notable changes.
- Do not scaffold speculatively; confirm scope with the user first.

### `third-party/` - paid APIs and systems
Thin client over a vendor service; no model weights, no upstream code.
- `src/<tool_pkg>/client.py` - vendor client (official SDK if available, else `httpx`); `core.py` calls it; `api.py` and `mcp_server.py` wrap `core.py`.
- Credentials only via environment variables, declared in the root `.env.example`. Never commit keys; never put keys in Postman files (use environment variables).
- `docs/COSTS.md` - pricing model, rate limits, quotas, and the cheapest way to test.
- Billable calls: MCP tool descriptions and the skill must say the call costs money; add a `dry_run`/estimate option where the vendor allows it. Agents must confirm with the user before running expensive or bulk jobs.
- Document the vendor docs URL and API version in `README.md`.

## Git

- The workspace root (`tools/`) is one git repo, default branch `main`. Each OS upstream is a submodule listed in `.gitmodules`.
- Fresh clone: `git clone --recurse-submodules <url>`. Already cloned without it: `git submodule update --init --recursive`.
- This clone is configured with `submodule.recurse=true` and `fetch.recurseSubmodules=on-demand`, so `git fetch` / `git pull` also fetch and update submodules. On a new machine run: `git config submodule.recurse true && git config fetch.recurseSubmodules on-demand`.
- Bump an upstream deliberately: `git -C <upstream> fetch && git -C <upstream> checkout <new-ref>`, test, then commit the new submodule pointer and update the pin in the tool README.
- Never commit: `.env`, `.venv/`, `models/`, `outputs/` (all gitignored). Commit `uv.lock`.
- Secret scanning: a Gitleaks pre-commit hook (`.pre-commit-config.yaml`, rules in `.gitleaks.toml`) blocks commits containing secrets. Per clone: `uv tool install pre-commit && pre-commit install --install-hooks`. Run all hooks with `pre-commit run --all-files`. If a finding is a false positive, allowlist it in `.gitleaks.toml` (never bypass with `--no-verify`); if it is real, rotate the key.
- Linting: Ruff check and Ruff format both run as pre-commit hooks (config in `ruff.toml`, rules E/F/W/I/B/UP, line length 120). Submodules (`**/upstream`) are excluded with `force-exclude`, so third-party code is never linted or formatted. Run manually with `uvx ruff check .` and `uvx ruff format .`. Fix findings in our code; do not add per-line ignores without a reason.
- Import order caveat: anything that must run before torch/huggingface imports (env + cache dirs) belongs in the package `__init__.py`, not in an import that the sorter can reorder.
- Commit/push only when the user asks.

## Environment variables: one shared `.env`

- All configuration and secrets live in `tools/.env` (gitignored). `tools/.env.example` is the committed template and lists every variable any tool uses.
- When a tool needs a new variable, add it to `.env.example` in the same change, under that tool's domain/category section, prefixed with the tool or vendor name (`ELEVENLABS_API_KEY`, `KOKORO_PORT`), with a comment if non-obvious. Do not create per-tool `.env.example` files.
- Tools load the root file by walking up from their own folder, so it works from any depth. Add `python-dotenv` (`uv add python-dotenv`) and in `core.py`:
  ```python
  from pathlib import Path
  from dotenv import load_dotenv

  _here = Path(__file__).resolve()
  _root = next(p for p in _here.parents if (p / "INSTRUCTIONS.md").exists())  # tools/
  load_dotenv(_root / ".env")  # shared; real env vars still win
  load_dotenv(_here.parents[2] / ".env", override=True)  # optional tool-local overrides
  ```
  A tool-local `.env`, if present, overrides the root one. Never print or log values.
- Launch configs for agents (`docs/AGENTS.md`) should not inline secrets; rely on the root `.env`, or reference it via `uv run --env-file <abs path>/tools/.env`.
- Postman environments mirror only the variables the collection needs, with empty values.

## 1. Python environment: uv, one venv per tool

- If the code is Python, use **uv**. Never use bare `pip`, `python -m venv`, or a shared/global environment.
- Each tool folder is its own uv project with its own `.venv` (`cd <domain>/<category>/<tool> && uv init && uv sync`). Do not create one venv at the workspace root.
- Declare dependencies with `uv add <pkg>` (dev deps: `uv add --dev <pkg>`); commit `pyproject.toml` and `uv.lock`, ignore `.venv/`.
- Run everything through uv: `uv run python ...`, `uv run uvicorn ...`, `uv run pytest`. MCP/agent configs must launch via `uv run --directory <abs tool path> ...` so the tool's own venv is used.
- Pin `requires-python` in `pyproject.toml`. Use a `src/` layout.
- Non-Python tools: use the idiomatic per-folder toolchain (e.g. `package.json` + local `node_modules`), still isolated per tool.

## 2. API + MCP + docs for every tool

Every tool must expose its functionality two ways, both thin wrappers over the same `core` code (no logic duplicated):

**HTTP API (Postman-invokable)**
- FastAPI app; serves OpenAPI at `/openapi.json` and docs at `/docs`.
- Include `GET /health`.
- Ship a Postman collection and environment in `postman/` (base URL as `{{baseUrl}}`, secrets as environment variables, never hardcoded). The collection must cover every endpoint with example bodies. It should also import cleanly from `/openapi.json`.
- Document in `docs/API.md`: how to start the server (`uv run uvicorn ...`), each endpoint with request/response examples and curl, auth, error format, and how to import the Postman collection.

**MCP server**
- Expose each capability as an MCP tool with a clear name, description and typed input schema. Support stdio transport (default) and, where useful, streamable HTTP.
- Document in `docs/MCP.md`: tool list with params and examples, transport, env vars, and how to test it (e.g. MCP Inspector).
- Document in `docs/AGENTS.md`: ready-to-paste config for each agent, with absolute paths and `uv run --directory`:
  - Claude Code: `claude mcp add <tool> -- uv run --directory <path> <entrypoint>` or `.mcp.json`
  - Cursor: `.cursor/mcp.json`
  - OpenCode: `opencode.json` (`mcp` section)
  - Pi: its MCP/extension config
- Keep API and MCP docs in sync with the code whenever endpoints or tools change.

## 3. A user-invocable skill per tool

- Each tool gets a skill at `<domain>/<category>/<tool>/skills/<tool>/SKILL.md` with frontmatter (`name`, `description`) so it can be invoked as `/<tool>`. The description must say what the tool does and when to use it.
- The skill body tells the agent how to use the tool: prefer the MCP tools, fall back to the HTTP API, with example invocations and expected output.
- Make it discoverable by linking it into agent skill directories (symlink, don't copy):
  - Claude Code: `.claude/skills/<tool>` (workspace) or `~/.claude/skills/<tool>`
  - Cursor / OpenCode / Pi: link or reference per each agent's skill/rules location, noted in `docs/AGENTS.md`.

## Definition of done for a new tool

- [ ] `uv sync` works from a clean checkout inside the tool folder
- [ ] API starts, `/health` returns 200, `/docs` renders
- [ ] Postman collection imports and requests succeed against a running server
- [ ] MCP server starts over stdio and lists its tools
- [ ] `docs/API.md`, `docs/MCP.md`, `docs/AGENTS.md`, `README.md` written
- [ ] Tool is placed in the right `<domain>/<category>/` folder and has the category-specific files above
- [ ] Licenses recorded: upstream URL, pinned ref, code + weights license in the tool README, and a row in `docs/legal/LICENSE-NOTES.md`
- [ ] Acknowledgement added in `docs/ACKNOWLEDGEMENTS.md` for every new submodule and key dependency
- [ ] Skill created, linked, and invocable as `/<tool>`
