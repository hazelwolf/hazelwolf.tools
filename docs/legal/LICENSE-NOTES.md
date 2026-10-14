# Licenses of included and used third-party material

Our own code is under the [Apache License 2.0](../../LICENSE). The items below are separate works with their own
terms. Check each upstream project for the authoritative text before relying on this summary.

## Open-source submodules (`<domain>/os/<tool>/upstream`)

| Tool | Upstream | Code license | Model weights license |
|---|---|---|---|
| audio-gen/os/audiocraft | https://github.com/facebookresearch/audiocraft | MIT (`upstream/LICENSE`) | **CC-BY-NC 4.0 - non-commercial only** (`upstream/LICENSE_weights`) |
| audio-gen/os/voicestudio | https://github.com/debpalash/VoiceStudio | AGPL-3.0-only (`upstream/LICENSE`); bundled `omnivoice/` Apache-2.0 | Default `k2-fsa/OmniVoice`: **CC-BY-NC - non-commercial only**; other engines vary |

Submodules are referenced, not copied: this repo stores only a pinned commit pointer. Our wrapper code
(`src/`, docs, skills) is Apache 2.0; it does not change the upstream's license.

### AudioCraft weights (non-commercial)

The pretrained MusicGen, MusicGen-Style, AudioGen, MAGNeT, JASCO, EnCodec, Multi-Band Diffusion and AudioSeal
weights are downloaded on first use from Hugging Face and are licensed **CC-BY-NC 4.0**. Do not use them, or
audio generated with them, commercially unless the model owner's license allows it. Our Apache 2.0 license does
not grant you rights to the weights.

### VoiceStudio (AGPL code, non-commercial default weights)

The VoiceStudio application is AGPL-3.0: commercial use is allowed, but a modified version offered over a network
must publish its source. We do not modify it; our wrapper talks to it over HTTP. The default OmniVoice weights are
CC-BY-NC. See `audio-gen/os/voicestudio/LICENSE-NOTES.md`.

## Third-party paid APIs (`<domain>/third-party/<tool>`)

Use is governed by each vendor's terms of service and usage policies, not by this repo's license. Record the
vendor's terms URL and any restrictions (commercial use, voice cloning, output ownership) in the tool's README.

## Adding a tool

Record in the tool README: upstream URL, pinned commit/tag, code license, weights license, and whether
commercial use is allowed. Add a row here for open-source tools.
