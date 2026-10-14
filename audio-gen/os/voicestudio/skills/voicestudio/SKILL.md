---
name: voicestudio
description: >-
  Local text to speech in 646 languages, voice cloning from a reference recording, and audio transcription via
  VoiceStudio (OmniVoice). Use when the user wants to speak or narrate text, generate a voiceover or WAV, clone or
  reuse a voice, list saved voices, or transcribe an audio file to text.
---

# VoiceStudio

Runs locally. Prefer the MCP tools (`voicestudio` server). Fall back to the HTTP API if MCP is not connected.

Tool dir: `/Users/bhomit.bhandari/Projects/gen.ai/hazelwolf.tools/audio-gen/os/voicestudio`

## 0. Make sure the backend is up

Call `check_health`. If `backend_ready` is false or the backend is unreachable, start it in the background, then
poll `check_health` until it is ready (10–60 s):

```bash
uv run --directory /Users/bhomit.bhandari/Projects/gen.ai/hazelwolf.tools/audio-gen/os/voicestudio voicestudio-backend
```

## MCP

- `generate_speech` writes a WAV and returns its path:
  ```json
  {"text": "Your build is done.", "language": "en", "instruct": "narrator", "output_name": "build-done"}
  ```
  Returns `{"path": ".../outputs/build-done.wav", "duration_s": 1.8, ...}`. Play it on macOS with `afplay <path>`.
- `list_voices` lists voices. Pass a voice's `id` as `profile_id` to speak in it.
- `clone_voice` takes `{"name": "Me", "ref_audio_path": "/abs/me.wav"}` (5–30 s, one clean speaker) and returns
  `profile_id`. For a one-off clone without saving, pass `ref_audio_path` to `generate_speech` instead.
- `transcribe` takes `{"audio_path": "/abs/clip.m4a"}` and returns `{"text": ...}`. Use `mode: "accurate"` for word
  timings.
- `list_personalities` lists style presets. Put a preset's text in `instruct`.

Notes:
- The first generation downloads the OmniVoice model (~2.3 GB). Tell the user it may take a few minutes.
- Clone a voice only if the user has the speaker's permission. `delete_voice` is irreversible, so confirm first.
- The default weights are non-commercial (CC-BY-NC).

## HTTP fallback

```bash
uv run --directory /Users/bhomit.bhandari/Projects/gen.ai/hazelwolf.tools/audio-gen/os/voicestudio voicestudio-api   # :8103
curl -s localhost:8103/generate -H 'Content-Type: application/json' -d '{"text":"Hello","language":"en"}'
curl -s -F name=Me -F ref_audio=@me.wav localhost:8103/voices/clone
curl -s -F audio=@clip.wav localhost:8103/transcribe
```

Details: `docs/MCP.md`, `docs/API.md`.
