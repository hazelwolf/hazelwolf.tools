# MCP server

```bash
uv run --directory <tool dir> voicestudio-mcp                               # stdio (default)
uv run --directory <tool dir> voicestudio-mcp --transport streamable-http   # http://127.0.0.1:8104/mcp
```

The tools call the upstream backend, so it must be running: `uv run --directory <tool dir> voicestudio-backend`.
`check_health` reports `backend_ready: false` until it is up.

Audio goes in and out as **local file paths**, so no base64 enters the agent's context.

## Tools

| Tool | Params | Returns |
|---|---|---|
| `check_health` | – | readiness, version, device |
| `list_voices` | – | `[{id, name, kind, language, ...}]` |
| `list_personalities` | – | style presets and their instruct text |
| `generate_speech` | `text`, `profile_id?`, `language="Auto"`, `instruct?`, `speed=1.0`, `steps?`, `seed?`, `ref_audio_path?`, `ref_text?`, `output_name?` | `{path, name, bytes, audio_id, duration_s, generation_time_s}` |
| `clone_voice` | `name`, `ref_audio_path`, `ref_text=""`, `language="Auto"`, `instruct=""` | `{profile_id, name, kind}` |
| `delete_voice` | `profile_id` | `{deleted}` |
| `transcribe` | `audio_path`, `language?`, `mode?` (`fast`/`accurate`/`reference`) | `{text, language, ...}` |

Examples:

```json
{"tool": "generate_speech", "arguments": {"text": "Build finished.", "language": "en", "instruct": "narrator"}}
{"tool": "clone_voice", "arguments": {"name": "Me", "ref_audio_path": "/Users/me/me.wav"}}
{"tool": "generate_speech", "arguments": {"text": "Namaste!", "profile_id": "3f2a...", "language": "hi"}}
{"tool": "transcribe", "arguments": {"audio_path": "/Users/me/clip.m4a"}}
```

Errors come back as tool errors with the backend's message (for example "backend is not reachable ... start it with ...").

## Environment

Read from `tools/.env`: `VOICESTUDIO_BACKEND_URL` (or `_HOST`/`_PORT`), `VOICESTUDIO_BACKEND_API_KEY`,
`VOICESTUDIO_OUTPUT_DIR`, `VOICESTUDIO_MCP_PORT`, `VOICESTUDIO_TIMEOUT_S`. See the README.

## Testing

```bash
npx @modelcontextprotocol/inspector uv run --directory <tool dir> voicestudio-mcp
```

## Upstream MCP

The backend also mounts its own MCP endpoint at `http://127.0.0.1:3900/mcp/` with similar tools. It supports
per-agent voice bindings via the `X-OmniVoice-Client-Id` header. Our launcher puts it in files mode, writing to
`outputs/`. Use ours for stdio and file paths. Use upstream's for its streamable HTTP and per-agent voice bindings.
