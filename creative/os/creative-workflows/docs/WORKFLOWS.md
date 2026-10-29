# Workflows

Official ComfyUI workflows, copied from the bundled templates into `workflows/`. Load them in the UI with Workflow > Open. They use subgraphs. Models are not installed yet, see the lists below.

## Person swap: `workflows/swap_person_scail2_int8.json`

SCAIL-2 character replacement. It tracks the person in the driving video with SAM3, then replaces them with the person in the reference image. The original background stays. The int8 model is the variant that fits 12 GB VRAM.

Inputs: driving video (`pose_video`), reference image of the new person, and a prompt describing the output. Keep the reference framing similar to the video, for example full body to full body.

Settings:
- `replace_mode` true (default) swaps the person. False animates the reference image instead.
- `sam3_video_object` and `sam3_image_object` are the SAM3 text prompts. The default is `human`. Use something more specific in a crowded scene, such as `man playing guitar`.
- `width` x `height`: start at 896x512. `frame_count` 81.
- `turbo_mode` uses the lightx2v preset for fast previews. Turn it off for final renders.
- Longer clips: each segment is 76 new frames. Run the Base subgraph first, then duplicate Extend and chain `previous_frames`, increasing `segment_index`. There is no automatic loop, so run each segment yourself.

Models:

| File | Folder |
| --- | --- |
| `wan2.1_14B_SCAIL_2_int8_convrot.safetensors` | `diffusion_models` |
| `wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` | `loras` |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` (installed) | `loras` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders` |
| `clip_vision_h.safetensors` | `clip_vision` |
| `Wan2_1_VAE_bf16.safetensors` | `vae` |
| `sam3.1_multiplex_fp16.safetensors` | `checkpoints` |

Sources are listed in the template's note, under Model Links (Comfy-Org/SCAIL-2, Comfy-Org/Wan_2.1_ComfyUI_repackaged, Comfy-Org/sam3.1 on Hugging Face).

## Lip sync

The audio is the original, so there is no separate lip-sync model. The swapped person's mouth follows the driving video, and the original audio is added back onto the output video. How closely SCAIL-2 matches the original mouth movement has not been tested.

`workflows/lipsync_infinitetalk.json` is an audio-driven option for new audio. It makes a video from a still image plus audio and cannot re-sync an existing video. Its models are not downloaded: `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` (15.5 GB, `diffusion_models`), `wan2.1_infiniteTalk_multi_fp16.safetensors` (`model_patches`), `wav2vec2-chinese-base_fp16.safetensors` (`audio_encoders`).

## Upscale: `workflows/upscale_video_seedvr2.json`

SeedVR2 3B int8 video upscale. Run it last on the swapped video.

Models: `seedvr2_3b_int8_convrot.safetensors` (`diffusion_models`), `seedvr2_ema_vae_fp16.safetensors` (`vae`).

## Order

1. Swap with SCAIL-2 at 896x512.
2. Upscale with SeedVR2.
3. Optionally interpolate frames with `Frame Interpolation` from `blueprints/`.

## Running workflows from agents

`workflows/*.json` are UI-format templates. To run one without the UI, use `creative/custom/comfyflow`: it runs
API-format copies in `workflows/api/` by name (`z_image_turbo`, `video_ltx2_3_id_lora`). Run a workflow once in the
UI, then `comfyflow import <name>` saves it there. See `creative/custom/comfyflow/README.md`.
