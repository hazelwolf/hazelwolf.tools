"""MCP server (stdio by default; --transport streamable-http for HTTP).

Audio moves by file path, never base64, so nothing large enters the agent's context.
"""

from __future__ import annotations

import argparse

import anyio
from mcp.server.fastmcp import FastMCP

from . import config, core

mcp = FastMCP("voicestudio", host=config.API_HOST, port=config.MCP_PORT)


async def _run(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except core.ServiceError as e:
        raise ValueError(str(e)) from None


@mcp.tool()
async def check_health() -> dict:
    """Check the VoiceStudio backend: readiness, version and active compute device (cuda/mps/cpu)."""
    return await _run(core.health)


@mcp.tool()
async def list_voices() -> list[dict]:
    """List saved voice profiles (id, name, kind clone/design, language). Pass an id to generate_speech."""
    return await _run(core.list_voices)


@mcp.tool()
async def list_personalities() -> list | dict:
    """List voice personality presets (Narrator, Casual, News Anchor, ...) and their instruct text."""
    return await _run(core.list_personalities)


@mcp.tool()
async def generate_speech(
    text: str,
    profile_id: str | None = None,
    language: str = "Auto",
    instruct: str | None = None,
    speed: float = 1.0,
    steps: int | None = None,
    seed: int | None = None,
    ref_audio_path: str | None = None,
    ref_text: str | None = None,
    output_name: str | None = None,
) -> dict:
    """Text to speech. Writes a WAV to the tool's outputs/ folder and returns its absolute path.

    Args:
        text: Text to speak. Long text is chunked at sentence boundaries automatically.
        profile_id: Saved voice from list_voices; omit for the default voice.
        language: ISO 639 code (en, hi, fr, ...) or Auto. 646 languages.
        instruct: Style instruction, e.g. 'whisper', 'excited', 'narrator'.
        speed: 0.5-2.0.
        steps: Diffusion steps: 8 draft, 16 balanced, 32 quality.
        seed: Fix for reproducible output.
        ref_audio_path: One-off zero-shot clone from a local audio file (instead of a saved profile).
        ref_text: Transcript of ref_audio_path (improves cloning).
        output_name: Output file stem.

    The first call on a fresh machine downloads the model (~2.3 GB) and can take several minutes.
    """
    return await _run(
        core.generate,
        text=text,
        profile_id=profile_id,
        language=language,
        instruct=instruct,
        speed=speed,
        steps=steps,
        seed=seed,
        ref_audio_path=ref_audio_path,
        ref_text=ref_text,
        output_name=output_name,
    )


@mcp.tool()
async def clone_voice(
    name: str, ref_audio_path: str, ref_text: str = "", language: str = "Auto", instruct: str = ""
) -> dict:
    """Save a reusable voice profile from a local reference recording (5-30 s, one clean speaker).
    Only clone voices you have permission to use. Returns profile_id for generate_speech."""
    return await _run(core.clone_voice, name, ref_audio_path, ref_text, language, instruct)


@mcp.tool()
async def delete_voice(profile_id: str) -> dict:
    """Delete a saved voice profile. Irreversible; confirm with the user first."""
    return await _run(core.delete_voice, profile_id)


@mcp.tool()
async def transcribe(audio_path: str, language: str | None = None, mode: str | None = None) -> dict:
    """Speech to text for a local audio file (wav/mp3/flac/ogg/m4a/webm).

    Args:
        audio_path: Absolute path to the audio file.
        language: Optional language hint; omit to auto-detect.
        mode: fast (default), accurate (word timings) or reference.
    """
    return await _run(core.transcribe, audio_path, language, mode)


def main():
    parser = argparse.ArgumentParser(description="VoiceStudio MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
