# VoiceStudio license notes

- **Upstream code** (`upstream/`): AGPL-3.0-only. Commercial use of the application is allowed. If you modify it and
  offer the modified version over a network, you must publish your modified source under the AGPL. We do not modify
  upstream; our wrapper (`src/`) talks to it over HTTP and stays Apache 2.0.
- **Bundled `omnivoice/` package**: Apache-2.0.
- **Default weights `k2-fsa/OmniVoice`**: CC-BY-NC, so **non-commercial use only**. Its `audio_tokenizer/` carries
  separate Boson Higgs Audio 2 and Meta Llama community terms.
- **Other engines** (Kokoro, Chatterbox, Qwen3-TTS, Supertonic, PocketTTS, ...) and ASR models (Whisper, Parakeet,
  pyannote) each keep their own licenses. Check the model card before you rely on one commercially.
- **Voice cloning**: clone a person's voice only with their consent.

The binding terms are the upstream `LICENSE`, `LICENSE-NOTICE.md`, and each model card on Hugging Face.
