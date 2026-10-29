# Acknowledgements

This workspace exists because of the open-source community. To everyone who writes, documents, maintains, reviews
and shares open-source software and research: **thank you.** Your work is the foundation these tools are built on,
and we are grateful for it.

Third-party projects keep their own licenses; see [legal/LICENSE-NOTES.md](legal/LICENSE-NOTES.md). Please
star, cite and support the projects below.

## Open-source projects included as submodules

### AudioCraft - Meta FAIR (Fundamental AI Research)

- Repository: https://github.com/facebookresearch/audiocraft
- Used in: `audio-gen/os/audiocraft`

Thank you to the AudioCraft authors and the FAIR Speech & Audio team at Meta for building the library and
releasing the code and pretrained models. It provides the models we wrap with an API, an MCP server and a skill:

| Model | Paper |
|---|---|
| MusicGen | *Simple and Controllable Music Generation* (Copet et al., 2023) |
| MusicGen-Style | *Audio Conditioning for Music Generation via Discrete Bottleneck Features* (Rouard et al., 2024) |
| AudioGen | *AudioGen: Textually Guided Audio Generation* (Kreuk et al., 2022) |
| MAGNeT / Audio-MAGNeT | *Masked Audio Generation using a Single Non-Autoregressive Transformer* (Ziv et al., 2024) |
| JASCO | *Joint Audio And Symbolic Conditioning for Temporally Controlled Text-To-Music Generation* (Tal et al., 2024) |
| EnCodec | *High Fidelity Neural Audio Compression* (Defossez et al., 2022) |
| Multi-Band Diffusion | *From Discrete Tokens to High-Fidelity Audio Using Multi-Band Diffusion* (San Roman et al., 2023) |
| AudioSeal | *Proactive Detection of Voice Cloning with Localized Watermarking* (San Roman et al., 2024) |

If you use these models in research, please cite the papers above. The pretrained weights are released for
non-commercial use (CC-BY-NC 4.0).

### VoiceStudio - Palash Debnath and contributors

- Repository: https://github.com/debpalash/VoiceStudio
- Used in: `audio-gen/os/voicestudio`

Thank you to Palash Debnath and the VoiceStudio contributors for an open, local-first voice studio. It gives us voice
cloning, multilingual TTS and transcription behind one backend. Thanks also to Han Zhu and the
[k2-fsa](https://github.com/k2-fsa/OmniVoice) team for **OmniVoice**, the default zero-shot TTS model, and to the
WhisperX, faster-whisper, MLX and sherpa-onnx projects it builds on.

### ComfyUI - Comfy-Org and contributors

- Repository: https://github.com/Comfy-Org/ComfyUI
- Used in: `creative/os/creative-workflows`

Thank you to comfyanonymous and the ComfyUI contributors for the node-based creative workflow host. The code is GPL-3.0. We pin it as a submodule and keep models and workflows beside that checkout.

<!-- Add one section per new submodule: name, repo URL, where it is used, what it gives us, thanks. -->

## Libraries and tools we depend on

Thank you to the maintainers of:

- [PyTorch](https://pytorch.org) and [xFormers](https://github.com/facebookresearch/xformers) - model runtime
- [Hugging Face Hub](https://github.com/huggingface/huggingface_hub) - hosting and downloading model weights
- [Demucs](https://github.com/facebookresearch/demucs) - drum stem separation for JASCO
- [AudioSeal](https://github.com/facebookresearch/audioseal) - audio watermarking
- [FastAPI](https://github.com/fastapi/fastapi), [Pydantic](https://github.com/pydantic/pydantic) and
  [Uvicorn](https://github.com/encode/uvicorn) - the HTTP APIs
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk) - the MCP servers
- [python-soundfile](https://github.com/bastibe/python-soundfile) - audio reading and writing
- [uv](https://github.com/astral-sh/uv) and [Ruff](https://github.com/astral-sh/ruff) - environments and linting
- [pre-commit](https://github.com/pre-commit/pre-commit) and [Gitleaks](https://github.com/gitleaks/gitleaks) -
  commit-time checks

And to the countless contributors of the transitive dependencies we never see.

## Contributing back

If these tools help you, consider starring the upstream repositories, reporting issues, sending fixes, citing the
papers, and sponsoring the maintainers.
