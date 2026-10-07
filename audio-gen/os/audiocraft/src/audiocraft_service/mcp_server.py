"""MCP server (stdio by default; --transport streamable-http for HTTP)."""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP

from . import (
    config,
    core,
)
from .errors import ServiceError
from .schemas import (
    AudioInput,
    Chord,
    CodecReconstructRequest,
    ContinuationRequest,
    GenerateRequest,
    JascoRequest,
    MbdRegenerateRequest,
    MelodyRequest,
    OutputOptions,
    SamplingParams,
    UnconditionalRequest,
    WatermarkDetectRequest,
    WatermarkEmbedRequest,
)

mcp = FastMCP("audiocraft", host=config.API_HOST, port=int(os.environ.get("AUDIOCRAFT_MCP_PORT", "8102")))

async def _run(fn, *args):
    """Run blocking inference off the event loop; keep stdout clean for the stdio protocol."""
    def call():
        with contextlib.redirect_stdout(sys.stderr):
            try:
                out = fn(*args)
            except ServiceError as e:
                raise ValueError(str(e)) from None
            return out.model_dump(exclude_none=True) if hasattr(out, "model_dump") else out
    return await anyio.to_thread.run_sync(call)


def _out(fmt: str, include_base64: bool = False) -> OutputOptions:
    return OutputOptions(format=fmt, include_base64=include_base64)  # type: ignore[arg-type]


def _params(duration: float | None, params: dict[str, Any] | None) -> SamplingParams:
    return SamplingParams(**({"duration": duration} if duration else {}), **(params or {}))


@mcp.tool()
async def list_models() -> dict:
    """List every AudioCraft model (MusicGen, MusicGen-Style, AudioGen, MAGNeT, JASCO), codecs, MBD and watermark
    options with capabilities, sample rate and approximate VRAM needs. Call this first to pick a model id."""
    return core.list_models()


@mcp.tool()
async def status() -> dict:
    """Show device, GPU memory and which models are currently loaded."""
    return core.status()


@mcp.tool()
async def unload_models() -> dict:
    """Free GPU memory by unloading all loaded models."""
    return await _run(core.unload_all)


@mcp.tool()
async def generate_audio(model: str, prompts: list[str], duration: float | None = None,
                         seed: int | None = None, params: dict[str, Any] | None = None,
                         use_mbd: bool = False, format: str = "wav") -> dict:
    """Text to audio. Music: facebook/musicgen-* (small/medium/large/melody/stereo-*), facebook/magnet-*.
    Sound effects: facebook/audiogen-medium, facebook/audio-magnet-*. One file per prompt.
    `duration` in seconds (MAGNeT/JASCO are fixed length). `params` may hold: use_sampling, top_k, top_p, temperature,
    cfg_coef, two_step_cfg, extend_stride, max_cfg_coef, min_cfg_coef, decoding_steps, span_arrangement.
    `use_mbd` decodes with Multi-Band Diffusion (mono MusicGen only). First use of a model downloads weights.
    Returns local file paths in `files[].path`."""
    req = GenerateRequest(model=model, prompts=prompts, seed=seed, use_mbd=use_mbd,
                          params=_params(duration, params), output=_out(format))
    return await _run(core.generate, req)


@mcp.tool()
async def generate_unconditional(model: str, num_samples: int = 1, duration: float | None = None,
                                 seed: int | None = None, format: str = "wav") -> dict:
    """Generate audio with no text prompt (MusicGen / AudioGen / MusicGen-Style). Returns local file paths in `files[].path`."""
    req = UnconditionalRequest(model=model, num_samples=num_samples, seed=seed,
                               params=_params(duration, None), output=_out(format))
    return await _run(core.generate_unconditional, req)


@mcp.tool()
async def generate_with_melody(model: str, prompts: list[str], melody_audio_path: str,
                               duration: float | None = None, seed: int | None = None,
                               params: dict[str, Any] | None = None, use_mbd: bool = False,
                               style_eval_q: int | None = None, style_excerpt_length: float | None = None,
                               format: str = "wav") -> dict:
    """Text + melody audio -> music (facebook/musicgen-*melody*), or text + style reference audio
    (facebook/musicgen-style; style_eval_q / style_excerpt_length tune the style bottleneck). Returns local file paths in `files[].path`."""
    req = MelodyRequest(model=model, prompts=prompts, melody=AudioInput(path=melody_audio_path), seed=seed,
                        params=_params(duration, params), use_mbd=use_mbd, style_eval_q=style_eval_q,
                        style_excerpt_length=style_excerpt_length, output=_out(format))
    return await _run(core.generate_with_melody, req)


@mcp.tool()
async def continue_audio(model: str, audio_path: str, duration: float, prompts: list[str] | None = None,
                         prompt_duration: float | None = None, seed: int | None = None,
                         params: dict[str, Any] | None = None, format: str = "wav") -> dict:
    """Continue an existing audio clip (MusicGen, MusicGen-Style, AudioGen). `duration` is the TOTAL output length
    and must exceed the prompt length; `prompt_duration` trims the input to its first N seconds. Returns local file paths in `files[].path`."""
    req = ContinuationRequest(model=model, audio=AudioInput(path=audio_path), prompts=prompts,
                              prompt_duration=prompt_duration, seed=seed,
                              params=_params(duration, params), output=_out(format))
    return await _run(core.continue_audio, req)


@mcp.tool()
async def generate_jasco(model: str, prompts: list[str], chords: list[dict[str, Any]] | None = None,
                         drums_audio_path: str | None = None, drums_from_mix_path: str | None = None,
                         melody_salience_path: str | None = None, seed: int | None = None,
                         params: dict[str, Any] | None = None, format: str = "wav") -> dict:
    """JASCO: 10 s music controlled by text + chords [{"chord":"Am7","start":0.0},...] + drums stem
    (or a full mix whose drums are extracted with Demucs) + optional melody salience tensor (.th) for
    *-melody-* models. params: cfg_coef_all, cfg_coef_txt, euler, euler_steps. Returns local file paths in `files[].path`."""
    req = JascoRequest(
        model=model, prompts=prompts, seed=seed, params=_params(None, params), output=_out(format),
        chords=[Chord(**c) for c in chords] if chords else None,
        drums=AudioInput(path=drums_audio_path) if drums_audio_path else None,
        drums_from_mix=AudioInput(path=drums_from_mix_path) if drums_from_mix_path else None,
        melody_salience=AudioInput(path=melody_salience_path) if melody_salience_path else None)
    return await _run(core.generate_jasco, req)


@mcp.tool()
async def codec_reconstruct(audio_path: str, model: str = "facebook/encodec_32khz",
                            bandwidth_kbps: float | None = None, format: str = "wav") -> dict:
    """EnCodec encode -> decode round trip (neural audio compression). bandwidth_kbps (1.5/3/6/12/24) is for
    facebook/encodec_24khz only. Returns the reconstructed file and token shape. Returns local file paths in `files[].path`."""
    req = CodecReconstructRequest(audio=AudioInput(path=audio_path), model=model,  # type: ignore[arg-type]
                                  bandwidth_kbps=bandwidth_kbps, output=_out(format))
    return await _run(core.codec_reconstruct, req)


@mcp.tool()
async def mbd_regenerate(audio_path: str, bandwidth_kbps: float = 3.0, format: str = "wav") -> dict:
    """Re-synthesise audio through EnCodec 24 kHz + Multi-Band Diffusion (higher fidelity than plain EnCodec
    decoding). bandwidth_kbps: 1.5, 3 or 6. Returns local file paths in `files[].path`."""
    req = MbdRegenerateRequest(audio=AudioInput(path=audio_path), bandwidth_kbps=bandwidth_kbps,  # type: ignore[arg-type]
                               output=_out(format))
    return await _run(core.mbd_regenerate, req)


@mcp.tool()
async def watermark_embed(audio_path: str, message_bits: str | None = None, alpha: float = 1.0,
                          format: str = "wav") -> dict:
    """Embed an inaudible AudioSeal watermark (16-bit message, e.g. '1010101010101010'; random if omitted).
    Output is 16 kHz mono. Returns local file paths in `files[].path`."""
    req = WatermarkEmbedRequest(audio=AudioInput(path=audio_path), message_bits=message_bits, alpha=alpha,
                                output=_out(format))
    return await _run(core.watermark_embed, req)


@mcp.tool()
async def watermark_detect(audio_path: str, threshold: float = 0.5) -> dict:
    """Detect an AudioSeal watermark; returns probability, fraction of frames detected and decoded message bits."""
    req = WatermarkDetectRequest(audio=AudioInput(path=audio_path), threshold=threshold)
    return await _run(core.watermark_detect, req)


def main():
    ap = argparse.ArgumentParser(description="AudioCraft MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = ap.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
