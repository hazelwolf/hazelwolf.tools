"""Request/response models shared by the HTTP API and the MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .registry import RESOLUTIONS

AspectRatio = Literal["1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "1:2", "2:1", "1:3", "3:1"]
ImageFormat = Literal["png", "webp", "jpeg"]
CfgNorm = Literal["none", "global", "channel", "cfg_zero_star"]


class OutputOptions(BaseModel):
    format: ImageFormat = "png"
    include_base64: bool = Field(False, description="Also return the image bytes base64-encoded in the response.")


class SamplingParams(BaseModel):
    """Leave a field unset to use the default (50 steps / cfg 4.0, or 8 steps / cfg 1.0 when `fast`)."""

    num_steps: int | None = Field(None, ge=1, le=200)
    cfg_scale: float | None = Field(None, ge=0, description="Lower it if colours look oversaturated.")
    cfg_norm: CfgNorm = "none"
    timestep_shift: float = Field(3.0, gt=0)
    cfg_interval: tuple[float, float] = (0.0, 1.0)


class _Base(BaseModel):
    model: str | None = Field(None, description="Model id from GET /v1/models. Defaults to SENSENOVA_U1_MODEL.")
    aspect_ratio: AspectRatio | None = Field(None, description="Pick a trained resolution bucket.")
    width: int | None = Field(None, ge=256, le=4096, description="Explicit size; overrides aspect_ratio.")
    height: int | None = Field(None, ge=256, le=4096)
    seed: int = Field(42, description="Seed for reproducible output.")
    num_images: int = Field(1, ge=1, le=8)
    fast: bool = Field(False, description="Merge the model's 8-step LoRA (about 6x faster, slightly lower quality).")
    think: bool = Field(False, description="Let the model reason in a <think> block before drawing.")
    enhance: bool = Field(
        False,
        description="Rewrite the prompt with an external LLM first (U1_ENHANCE_* env vars). Billable API call.",
    )
    params: SamplingParams = Field(default_factory=SamplingParams)
    output: OutputOptions = Field(default_factory=OutputOptions)

    @model_validator(mode="after")
    def _size_pair(self):
        if (self.width is None) != (self.height is None):
            raise ValueError("Set both width and height, or neither")
        return self


class GenerateRequest(_Base):
    prompt: str = Field(..., min_length=1, description="Full image description. Long, specific prompts work best.")

    def size(self) -> tuple[int, int]:
        if self.width and self.height:
            return self.width, self.height
        return RESOLUTIONS[self.aspect_ratio or "1:1"]


class InfographicSection(BaseModel):
    heading: str
    points: list[str] = Field(default_factory=list, description="Short bullet texts rendered inside the section.")
    icon: str | None = Field(None, description="Icon or illustration idea for this section, e.g. 'shield with a lock'.")


class InfographicRequest(_Base):
    title: str = Field(..., min_length=1, description="Headline rendered at the top.")
    subtitle: str | None = None
    sections: list[InfographicSection] = Field(default_factory=list, max_length=8)
    style: str = Field(
        "modern flat vector design, clean grid, generous white space",
        description="Visual style, e.g. 'retro comic book', 'minimal Swiss tech', 'hand-drawn chalkboard'.",
    )
    palette: str | None = Field(None, description="Colour scheme, e.g. 'navy, teal and warm orange on off-white'.")
    layout: str | None = Field(None, description="e.g. 'three vertical columns', 'timeline left to right'.")
    language: str = Field("English", description="Language of all rendered text.")
    footer: str | None = Field(None, description="Small text at the bottom, e.g. a source line.")
    extra: str | None = Field(None, description="Anything else the image must contain or avoid.")
    prompt: str | None = Field(None, description="Use this full prompt instead of building one from the fields.")
    aspect_ratio: AspectRatio | None = Field("16:9", description="Infographics default to 16:9 (2720x1536).")

    def size(self) -> tuple[int, int]:
        if self.width and self.height:
            return self.width, self.height
        return RESOLUTIONS[self.aspect_ratio or "16:9"]


class ImageFile(BaseModel):
    name: str
    path: str
    url: str | None = None
    width: int
    height: int
    bytes: int
    base64: str | None = None


class GenerationResult(BaseModel):
    model: str
    prompt: str = Field(..., description="The prompt actually sent to the model (after building / enhancement).")
    files: list[ImageFile]
    seed: int
    num_steps: int
    cfg_scale: float
    fast: bool
    seconds: float
    think_text: str | None = None
    warnings: list[str] = Field(default_factory=list)
