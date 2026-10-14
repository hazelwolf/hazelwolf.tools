# VoiceStudio

Local voice cloning, text to speech in 646 languages, and transcription for agents. This wraps the
[VoiceStudio](https://github.com/debpalash/VoiceStudio) backend (default TTS model: k2-fsa/OmniVoice) with an HTTP API,
an MCP server and the `/voicestudio` skill.

| | |
|---|---|
| Upstream | https://github.com/debpalash/VoiceStudio (submodule at `upstream/`) |
| Pinned ref | `v0.5.6` (`3915a62cb482bb43117aaebab57d22745bd1cc21`) |
| Code license | AGPL-3.0-only (`upstream/LICENSE`, `upstream/LICENSE-NOTICE.md`). Bundled `omnivoice/` package is Apache-2.0 |
| Weights license | `k2-fsa/OmniVoice` weights are **CC-BY-NC (non-commercial only)**. Other engines have their own terms. See [LICENSE-NOTES.md](LICENSE-NOTES.md) |
| Commercial use | Not with the default weights |

## How it fits together

```
agent ── MCP (stdio) ──> voicestudio-mcp ─┐
curl / Postman ── HTTP :8103 ──> voicestudio-api ─┼─ core.py ── HTTP ──> upstream backend :3900 (models, voices DB)
                                                 ┘
```

The upstream backend is a long-running server that keeps models warm. Our `core.py` is a thin client over its REST
routes (`/generate`, `/profiles`, `/transcribe`, `/health`). Audio moves by file path: generated WAVs are written to
`outputs/`, so nothing large enters an agent's context.

## Setup

```bash
cd audio-gen/os/voicestudio
git submodule update --init upstream     # if the clone skipped submodules (do NOT init upstream's own submodules)
uv sync                                  # Python 3.11, torch 2.8 (MPS on Apple Silicon, CUDA 12.8 on Linux/Windows)
```

`uv sync` downloads about 6 GB of packages (torch, WhisperX, pyannote, mlx-audio and others).

## Run

Two processes: the upstream backend, then the wrapper you need.

```bash
uv run voicestudio-backend               # upstream backend on 127.0.0.1:3900; ready when /health returns 200
uv run voicestudio-api                   # our HTTP API on 127.0.0.1:8103 (docs at /docs)
uv run voicestudio-mcp                   # MCP over stdio (agents launch this themselves)
```

The backend answers `/health` with 503 while it starts (about 10–60 s), then 200. Check its environment with
`uv run voicestudio-backend --diagnose`.

## Models

Weights download on first use into `models/huggingface/` (gitignored). Voice profiles, references and history live in
`models/data/`.

| Model | Size | Use | Memory |
|---|---|---|---|
| k2-fsa/OmniVoice (default) | ~2.3 GB | Zero-shot clone + TTS, 646 languages | ~4–6 GB GPU/unified memory |
| Whisper (MLX on Apple Silicon, faster-whisper elsewhere) | 0.8–3 GB | Transcription | 2–4 GB |

The first `generate` call downloads OmniVoice, which takes a few minutes. To download it ahead of time, start the
backend and make one short generation. The models fit easily on this machine (M5 Max, 48 GB unified memory, MPS).
For a CUDA box, any GPU with 8 GB+ VRAM is enough. CPU works too, but slower.

## Configuration

All variables live in the root `tools/.env` (see `.env.example`, section `audio-gen / os`):

| Variable | Default | Purpose |
|---|---|---|
| `VOICESTUDIO_BACKEND_HOST` / `_PORT` | `127.0.0.1` / `3900` | Where the upstream backend binds |
| `VOICESTUDIO_BACKEND_URL` | from host/port | Point the wrapper at another backend, e.g. the desktop app or a GPU box |
| `VOICESTUDIO_BACKEND_API_KEY` | empty | Bearer key for a remote backend that requires one |
| `VOICESTUDIO_PORT` / `VOICESTUDIO_MCP_PORT` | `8103` / `8104` | Wrapper HTTP API / MCP streamable-HTTP port |
| `VOICESTUDIO_API_KEY` | empty | Optional bearer token for the wrapper HTTP API |
| `VOICESTUDIO_DATA_DIR` | `models/data` | Upstream state (voice profiles DB, references) |
| `VOICESTUDIO_MODELS_DIR` | `models` | HF cache lives in `<this>/huggingface` |
| `VOICESTUDIO_OUTPUT_DIR` | `outputs` | Generated WAVs |
| `VOICESTUDIO_DEVICE` | auto | `cuda`, `mps` or `cpu` |
| `VOICESTUDIO_TIMEOUT_S` | `1800` | Per-request wait (covers the first-run model download) |

The launcher also sets `OMNIVOICE_ANALYTICS_DISABLED=1` (no telemetry) and `PYTORCH_ENABLE_MPS_FALLBACK=1`.

## Also available from upstream

- The upstream backend has its own MCP endpoint at `http://127.0.0.1:3900/mcp/` and a Scalar API reference. Our
  launcher sets it to files mode (`outputs/`).
- The Electron desktop UI (dubbing, audiobooks, voice design) needs Bun and Node 22+. It runs from `upstream/`
  (`bun install && bun run dev`) and connects to the same backend.

## Docs

[docs/API.md](docs/API.md) · [docs/MCP.md](docs/MCP.md) · [docs/AGENTS.md](docs/AGENTS.md) ·
[skills/voicestudio/SKILL.md](skills/voicestudio/SKILL.md)

## Responsible use

Clone only voices you have permission to use. See [docs/legal/DISCLAIMER.md](../../../docs/legal/DISCLAIMER.md).

## Tests

```bash
uv run pytest     # mocks the backend; no models needed
```
