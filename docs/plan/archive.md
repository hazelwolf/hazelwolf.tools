# Kanban archive

Completed cards moved out of [KANBAN.md](KANBAN.md). Last updated: 2026-10-29.

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
| CW-6 | Creative workflows | Z-Image Turbo smoke test on the new ComfyUI setup (1024x1024 cold and warm, 1344x768, text rendering check) | Done | 3 of 3 runs succeeded: 18.6 s cold, about 12 s warm; about 8.6 GB VRAM used. Run over the API, not the GUI |
| VG-1 | Video-gen | Choose the first video-gen model / whether to build a custom tool | Done | Decision: use ComfyUI. LTX-2.3 22B fp8 timed on this GPU: 832x480 5 s with audio in 73 s cold; 1280x704 5 s in 89 s warm (about 3.4 s per step at 832, 5.3 s at 1280). Peak VRAM about 7.4 GB after the run |
| CW-6 | Creative workflows | Comfyflow: thin CLI, HTTP API and MCP wrapper that runs ComfyUI workflows by name (`creative/custom/comfyflow`) | Done | 13 unit tests pass. Tested live against ComfyUI 0.38.0: Z-Image Turbo (about 12 s) and LTX-2.3 talking-person video with file uploads (56 s for 3 s), via CLI, MCP stdio and the HTTP API; imported both from the UI run history |
