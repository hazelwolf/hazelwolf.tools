# Kanban tracker

Single source of truth for work on this workspace. Update it in the same change as the work.
Last updated: 2026-10-29.

**Rules:** one row per card. Change the `Status` cell and move the row to the matching section when status
changes. Mark a card `Done` only when it is verified, not just written.
Status values: `Blocked`, `To do`, `In progress`, `Done`.
Area codes: `AC` AudioCraft, `SN` SenseNova-U1, `PL` platform/workspace, `VG` video-gen.

## Summary

| Status | Cards |
|---|---|
| Blocked | 3 |
| In progress | 0 |
| To do | 38 |
| Done | 8 |

## Blocked / waiting on a decision

| ID | Area | Task | Status | Notes |
|---|---|---|---|---|
| PL-1 | Platform | Restart ComfyUI (`/path/to/ComfyUI`, `main.py --listen 127.0.0.1 --port 8188`) | Blocked | Stopped by mistake earlier; waiting for the owner to confirm |
| PL-3 | Platform | Confirm copyright holder in `NOTICE` ("HazelWolf") and add a security-reporting contact in `docs/legal/SECURITY.md` | Blocked | Needs owner input |
| VG-1 | Video-gen | Choose the first video-gen model to set up | Blocked | Candidates for 12 GB: Wan 2.2 TI2V-5B fp8, LTX-Video, Wan 2.1 1.3B |

## In progress

| ID | Area | Task | Status | Notes |
|---|---|---|---|---|
| - | - | _(nothing)_ | - | - |

## To do

GPU works again (driver 580-open). Already verified before the driver failure: `musicgen-small` text-to-audio
(wav, mp3), continuation, EnCodec 24/32 kHz round trips, request validation.

| ID | Area | Task | Status | Notes |
|---|---|---|---|---|
| AC-1 | AudioCraft | Re-run MBD decoding (`use_mbd`), unconditional generation and MBD regeneration | To do | Hit out-of-memory while ComfyUI held the GPU |
| AC-2 | AudioCraft | AudioSeal watermark embed and detect | To do | Pinned `audioseal==0.1.4`; 0.2.0 failed on torch 2.11 |
| AC-3 | AudioCraft | MAGNeT (`magnet-small-10secs`) and Audio-MAGNeT (`audio-magnet-small`) | To do | Fixed-length models |
| AC-4 | AudioCraft | JASCO: text only, chords, drums stem, drums from a mix (Demucs), melody salience | To do | Start with `jasco-chords-drums-400M` |
| AC-5 | AudioCraft | MusicGen melody, MusicGen-Style, stereo variants and AudioGen | To do | AudioGen / melody / style weights are large downloads |
| AC-6 | AudioCraft | VRAM check for medium / large / melody-large; confirm OOM returns a clean 507; record real numbers in the registry | To do | |
| AC-7 | AudioCraft | Test the MCP server over stdio (list tools, call `generate_audio`, `watermark_detect`) | To do | |
| AC-8 | AudioCraft | pytest suite (fast CPU checks plus GPU tests marked `gpu`) | To do | |
| AC-9 | AudioCraft | Postman collection and environment (`postman/`) | To do | Definition-of-done item |
| AC-10 | AudioCraft | `docs/API.md`, `docs/MCP.md`, `docs/AGENTS.md` (Claude, Cursor, OpenCode, Pi) | To do | Definition-of-done item |
| AC-11 | AudioCraft | `/audiocraft` skill (`skills/audiocraft/SKILL.md`) and link into agent skill folders | To do | Definition-of-done item |
| AC-12 | AudioCraft | Real `README.md`: pinned commit, licenses (code MIT, weights CC-BY-NC), VRAM table, setup/run | To do | Current README is an empty stub |
| AC-13 | AudioCraft | Optional `AUDIOCRAFT_ALLOWED_INPUT_DIRS` to restrict readable folders | To do | Referenced in `docs/legal/SECURITY.md` |
| AC-14 | AudioCraft | Commit the AudioCraft changes | To do | Only when the owner asks |
| SN-1 | SenseNova | Core engine (`core.py`): lazy model load, one-job GPU lock, LRU model cache, `vram_mode` (full/fast/balanced/low), resolution buckets, clean OOM error (507), seed handling | To do | Registry, config, schemas already written; port the logic from `upstream/examples/t2i/inference.py` |
| SN-2 | SenseNova | 8-step LoRA 'fast' mode: download/merge the model's LoRA on demand, switch cfg 1.0 and 8 steps, unmerge or reload when `fast` flips | To do | LoRA V2 file is already cached; registry has the repo/filename pairs |
| SN-3 | SenseNova | Text-to-image endpoint and MCP tool (`/v1/generate`): aspect ratio or explicit size, batch (`num_images`), `think` mode, output formats | To do | Request schema exists |
| SN-4 | SenseNova | Infographic endpoint and MCP tool (`/v1/infographic`): build the prompt from title, sections, style, palette, layout, footer, or accept a full prompt | To do | Request schema exists; reuse the engine-infographic prompt style that worked |
| SN-5 | SenseNova | Image editing endpoint and MCP tool (`upstream/examples/editing`): input image upload plus edit instruction | To do | Needs an `AudioInput`-style `ImageInput` (path / base64 / upload_id) |
| SN-6 | SenseNova | Interleaved text-and-image generation (`upstream/examples/interleave`) endpoint and MCP tool | To do | Returns text plus several images |
| SN-7 | SenseNova | Visual question answering / image understanding (`upstream/examples/vqa`) endpoint and MCP tool | To do | Text-out; no image output |
| SN-8 | SenseNova | Prompt enhancement (`enhance` option, `sensenova_u1.prompt_enhance` adapters): config for the external LLM, off by default | To do | Needs an LLM endpoint and key in `.env`; check privacy and cost wording |
| SN-9 | SenseNova | Optional GGUF checkpoint support (`SENSENOVA_U1_GGUF`) for lower VRAM | To do | Community Q8 files are about 20 GB; test only if wanted |
| SN-10 | SenseNova | HTTP API (`api.py`): `/health`, `/v1/models`, `/v1/status`, `/v1/unload`, `/v1/uploads`, `/v1/files`, optional bearer token, error handler | To do | Mirror the AudioCraft API layout |
| SN-11 | SenseNova | MCP server (`mcp_server.py`): tools for models, status, generate, infographic, edit, interleave, vqa, unload; stdout kept clean for stdio; real docstrings as descriptions | To do | Pin `mcp<2`; test over stdio |
| SN-12 | SenseNova | Add `SENSENOVA_U1_*` variables to the root `.env.example` (model, models dir, output dir, vram mode, budget, port, optional API key and enhance LLM) | To do | None are in the root file yet |
| SN-13 | SenseNova | GPU test pass on the 12 GB card: base and fast LoRA, 1:1 / 2:3 / 16:9 buckets, batch of 2, edit, interleave, VQA, OOM path, model switch | To do | Record real VRAM and timings in the registry |
| SN-14 | SenseNova | pytest suite (fast CPU checks plus GPU tests marked `gpu`); Ruff and Gitleaks clean | To do | Model download kept out of default test runs |
| SN-15 | SenseNova | Postman collection and environment (`postman/`) covering every endpoint with example bodies | To do | Definition-of-done item |
| SN-16 | SenseNova | Docs: `docs/API.md`, `docs/MCP.md`, `docs/AGENTS.md` (Claude, Cursor, OpenCode, Pi configs) | To do | Definition-of-done item |
| SN-17 | SenseNova | User-invocable `/sensenova` skill (`skills/sensenova/SKILL.md`), prefer MCP then API, with infographic prompt tips; link into agent skill folders | To do | Definition-of-done item |
| SN-18 | SenseNova | Real `README.md`: pinned commit `c35c83b`, licenses (check code and weights terms), model sizes (35 GB bf16), VRAM modes, setup and run | To do | Record licenses in `docs/legal/LICENSE-NOTES.md` and thanks in `docs/ACKNOWLEDGEMENTS.md` |
| SN-19 | SenseNova | Re-run the engine infographic with a shorter prompt (no circular cycle diagram) to cut label errors | To do | Follow-up from the comparison |
| SN-20 | SenseNova | Try `SenseNova-U1-8B-MoT-Infographic-V3` and compare against U1.5 base and LoRA | To do | About 35 GB download |
| SN-21 | SenseNova | Commit the SenseNova tool (submodule pointer, README, `uv.lock`, service code) | To do | Only when the owner asks |
| PL-2 | Platform | Fix two Ruff import-order findings in `media/custom/dropbox/tests/` | To do | `uvx ruff check media --fix` |
| PL-4 | Platform | Verify paper titles and authors in `docs/ACKNOWLEDGEMENTS.md` | To do | Written from memory |
| PL-5 | Platform | Fetch the `voicestudio` submodule | To do | `git submodule update --init audio-gen/os/voicestudio/upstream` |

## Done

| ID | Area | Task | Status | Notes |
|---|---|---|---|---|
| PL-6 | Platform | Workspace structure (`audio-gen`, `video-gen`, `image-gen`; `os` / `custom` / `third-party`) and `INSTRUCTIONS.md` | Done | |
| PL-7 | Platform | Shared `.env.example`, loaded from the workspace root by every tool | Done | |
| PL-8 | Platform | Git repo, OS upstreams as submodules, fetch/clone recursion configured | Done | |
| PL-9 | Platform | Gitleaks and Ruff pre-commit hooks (submodules excluded from linting) | Done | |
| PL-10 | Platform | Apache 2.0 `LICENSE`, `NOTICE`, `docs/legal/`, `docs/ACKNOWLEDGEMENTS.md`, root `README.md` | Done | |
| PL-11 | Platform | NVIDIA driver fixed: open 580 kernel module for the RTX PRO 3000 Blackwell | Done | Was loading the proprietary module |
| AC-0 | AudioCraft | Service: uv env (torch cu128 for Blackwell), HTTP API (20 routes), MCP server (12 tools), registry (22 models) | Done | Commit `15a51a1` |
| SN-0 | SenseNova | Submodule, uv env, U1.5-8B-MoT weights (35 GB) and 8-step LoRA, engine infographic, base vs LoRA comparison | Done | LoRA about 3x faster, similar quality; see `image-gen/os/sensenova-u1/outputs/compare/EVALUATION.md` |
