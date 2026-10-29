# Hardware

Profiled 2026-10-07. Use this to pick models instead of re-checking the specs.

| Component | Spec |
| --- | --- |
| GPU | NVIDIA RTX PRO 3000 Blackwell Generation Laptop GPU |
| VRAM | 12 GB (12227 MiB) |
| Driver | 595.84 |
| System RAM | 62 GB |
| CPU | 20 threads |
| Disk | 1.9 TB NVMe, about 1.6 TB free at profiling time |
| OS | Linux 7.0.0-31-generic |

## Model fit

- VRAM is the limit. Models above about 12 GB need offloading to system RAM, and the 62 GB of RAM handles that.
- 14B video models: use Q8_0 GGUF or fp8. Avoid Q4/Q5 when quality matters.
- Video generation is comfortable at 480x832. 720p needs block offloading and is slow.
- Blackwell supports fp8 and NVFP4 natively.

## Installed models (2026-10-07)

- checkpoints: `ltx-2.3-22b-dev-fp8`, `sam3.1_multiplex_fp16`
- diffusion_models: `humo_17B_fp8_e4m3fn`, `z_image_turbo_bf16`, `wan2.1_14B_SCAIL_2_int8_convrot`
- text_encoders: `umt5_xxl_fp8_e4m3fn_scaled` and others
- clip_vision: `clip_vision_h`
- vae: `Wan2_1_VAE_bf16`, `wan_2.1_vae`, `ae`
- loras: `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16`, `wan2.1_SCAIL_2_DPO_lora_bf16`, `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16`, `ltx-2.3-id-lora-talkvid-3k`
- latent_upscale_models: `ltx-2.3-spatial-upscaler-x2-1.1`
- audio_encoders: `whisper_large_v3_fp16`
- custom_nodes: none
