"""Request/response models shared by the HTTP API and the MCP server."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AudioFormat = Literal["wav", "mp3", "flac", "ogg"]
NormStrategy = Literal["loudness", "peak", "rms", "clip"]


class AudioInput(BaseModel):
    """Reference to input audio. Provide exactly one field."""

    path: str | None = Field(None, description="Absolute path on the machine running the server.")
    base64: str | None = Field(None, description="Base64-encoded audio file bytes (wav/mp3/flac/ogg...).")
    upload_id: str | None = Field(None, description="id returned by POST /v1/uploads.")

    @model_validator(mode="after")
    def _one_of(self):
        if sum(v is not None for v in (self.path, self.base64, self.upload_id)) != 1:
            raise ValueError("Provide exactly one of: path, base64, upload_id")
        return self


class OutputOptions(BaseModel):
    format: AudioFormat = "wav"
    normalize: NormStrategy = Field("loudness", description="Loudness normalisation strategy applied before saving.")
    include_base64: bool = Field(False, description="Also return the audio bytes base64-encoded in the response.")


class SamplingParams(BaseModel):
    """Generation parameters. Leave a field unset to use the model's default.
    Parameters a model family does not support are rejected with a 422."""

    duration: float | None = Field(None, gt=0, description="Seconds. Ignored (with a warning) for fixed-length models.")
    # MusicGen / AudioGen
    use_sampling: bool | None = None
    top_k: int | None = Field(None, ge=0)
    top_p: float | None = Field(None, ge=0, le=1)
    temperature: float | None = Field(None, gt=0)
    cfg_coef: float | None = Field(None, description="Classifier-free guidance strength.")
    cfg_coef_beta: float | None = Field(None, description="Double-CFG beta (MusicGen melody/style).")
    two_step_cfg: bool | None = None
    extend_stride: float | None = Field(None, gt=0, description="Stride (s) when generating past the model window.")
    # MAGNeT
    max_cfg_coef: float | None = None
    min_cfg_coef: float | None = None
    decoding_steps: list[int] | None = Field(None, description="MAGNeT steps per codebook, e.g. [20,10,10,10].")
    span_arrangement: Literal["nonoverlap", "stride1"] | None = None
    # JASCO
    cfg_coef_all: float | None = None
    cfg_coef_txt: float | None = None
    euler: bool | None = Field(None, description="JASCO: use fixed-step Euler solver instead of adaptive.")
    euler_steps: int | None = Field(None, ge=1)


class _Base(BaseModel):
    model: str = Field(..., description="Model id from GET /v1/models, e.g. facebook/musicgen-small.")
    seed: int | None = Field(None, description="Seed for reproducible output.")
    output: OutputOptions = OutputOptions()


class GenerateRequest(_Base):
    """Text -> audio. Works for MusicGen, AudioGen, MAGNeT, Audio-MAGNeT and text-only JASCO."""

    prompts: list[str] = Field(..., min_length=1, description="One audio file is produced per prompt.")
    params: SamplingParams = SamplingParams()
    use_mbd: bool = Field(False, description="Decode with Multi-Band Diffusion (mono MusicGen models only).")


class UnconditionalRequest(_Base):
    num_samples: int = Field(1, ge=1)
    params: SamplingParams = SamplingParams()


class MelodyRequest(_Base):
    """Text + melody (MusicGen *-melody*) or text + style audio (musicgen-style)."""

    prompts: list[str] = Field(..., min_length=1)
    melody: AudioInput
    params: SamplingParams = SamplingParams()
    use_mbd: bool = False
    style_eval_q: int | None = Field(None, ge=1, description="musicgen-style: RVQ streams for the style bottleneck.")
    style_excerpt_length: float | None = Field(None, gt=0, description="musicgen-style: excerpt seconds.")
    style_ds_factor: int | None = Field(None, ge=1)


class ContinuationRequest(_Base):
    """Continue an audio prompt (MusicGen, MusicGen-Style, AudioGen)."""

    audio: AudioInput
    prompts: list[str] | None = Field(None, description="Optional text conditioning for the continuation.")
    prompt_duration: float | None = Field(None, gt=0, description="Only use the first N seconds of the audio.")
    params: SamplingParams = SamplingParams()
    use_mbd: bool = False


class Chord(BaseModel):
    chord: str = Field(..., examples=["C", "Am7", "F#m", "N"])
    start: float = Field(..., ge=0, description="Start time in seconds.")


class JascoRequest(_Base):
    """Text + chords + drums (+ melody) -> 10 s music."""

    prompts: list[str] = Field(..., min_length=1)
    chords: list[Chord] | None = None
    drums: AudioInput | None = Field(None, description="Drums stem to follow.")
    drums_from_mix: AudioInput | None = Field(
        None, description="Full mix; the drums stem is extracted with Demucs (htdemucs). Exclusive with `drums`.")
    melody_salience: AudioInput | None = Field(
        None, description="Torch tensor file (.th/.pt) with a melody salience matrix [500,53] or [53,500]. "
                          "Needs a *-melody-* model.")
    params: SamplingParams = SamplingParams()


class CodecReconstructRequest(BaseModel):
    audio: AudioInput
    model: Literal["facebook/encodec_24khz", "facebook/encodec_32khz"] = "facebook/encodec_32khz"
    bandwidth_kbps: float | None = Field(None, description="24 kHz model only: 1.5, 3, 6, 12 or 24.")
    output: OutputOptions = OutputOptions()


class MbdRegenerateRequest(BaseModel):
    audio: AudioInput
    bandwidth_kbps: Literal[1.5, 3.0, 6.0] = 3.0
    output: OutputOptions = OutputOptions()


class WatermarkEmbedRequest(BaseModel):
    audio: AudioInput
    message_bits: str | None = Field(None, pattern=r"^[01]{16}$",
                                     description="16-bit message, e.g. '1010101010101010'.")
    alpha: float = Field(1.0, ge=0, le=2, description="Watermark strength.")
    output: OutputOptions = OutputOptions()


class WatermarkDetectRequest(BaseModel):
    audio: AudioInput
    threshold: float = Field(0.5, ge=0, le=1)


class OutputFile(BaseModel):
    name: str
    path: str
    url: str | None = None
    format: str
    bytes: int
    prompt: str | None = None
    base64: str | None = None


class GenerationResult(BaseModel):
    model: str
    sample_rate: int
    channels: int
    duration_s: float
    elapsed_s: float
    seed: int | None = None
    files: list[OutputFile]
    warnings: list[str] = []
    extra: dict = {}
