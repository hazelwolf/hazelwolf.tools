"""The models under test: the two the imagegen tool serves (Z-Image for general images, Boogu for text-heavy ones).

FLUX.2 klein 4B and Qwen-Image 2.1 Turbo were compared too (smoke run, 2026-11-12) and dropped: both miscounted
objects, and Qwen's license is non-commercial. Each one runs through mflux with its own recommended step count.

Both share mflux's interface: `Cls(quantize=, model_path=, model_config=)` and
`generate_image(seed=, prompt=, num_inference_steps=, width=, height=)`, so one runner drives them all.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

from . import config


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    repo: str
    revision: str  # Hugging Face commit the eval was set up against
    module: str
    cls: str
    config_fn: str  # ModelConfig static method
    steps: int
    license: str
    commercial: bool
    download_gb: float
    # Other folders that may already hold a quantized copy, as name templates with {bits}.
    reuse: tuple[tuple[Path, str], ...] = field(default=())

    def _tag(self, bits: int | None) -> str:
        return f"q{bits}" if bits else "bf16"

    def local_path(self, bits: int | None = None) -> Path:
        bits = config.QUANTIZE if bits is None else bits
        return config.MODELS_DIR / f"{self.key}-{self._tag(bits)}"

    def weight_path(self, bits: int | None = None) -> Path:
        """The first ready copy (a reused one wins), else where prepare will save one."""
        bits = config.QUANTIZE if bits is None else bits
        for folder, name in self.reuse:
            p = folder / name.format(tag=self._tag(bits))
            if weights_ready(p):
                return p
        return self.local_path(bits)

    def model_class(self):
        return getattr(importlib.import_module(self.module), self.cls)

    def model_config(self):
        from mflux.models.common.config import ModelConfig

        return getattr(ModelConfig, self.config_fn)()


def weights_ready(path: Path) -> bool:
    return (path / "transformer").is_dir()


MODELS: dict[str, ModelSpec] = {
    m.key: m
    for m in (
        ModelSpec(
            key="zimage",
            label="Z-Image-Turbo (6B)",
            repo="Tongyi-MAI/Z-Image-Turbo",
            revision="f332072aa78be7aecdf3ee76d5c247082da564a6",
            module="mflux.models.z_image",
            cls="ZImage",
            config_fn="z_image_turbo",
            steps=9,
            license="Apache-2.0",
            commercial=True,
            download_gb=32.9,
            reuse=((config.IMAGEGEN_MODELS_DIR, "z-image-turbo-{tag}"),),
        ),
        ModelSpec(
            key="boogu",
            label="Boogu Image 0.1 Turbo (10B)",
            repo="Boogu/Boogu-Image-0.1-Turbo",
            revision="53ad54522023f64d049f7f38e4d679359ef3fb92",
            module="mflux.models.boogu",
            cls="BooguImage",
            config_fn="boogu_image_turbo",
            steps=8,  # mflux: 4 steps up to ~768 px, 8 at 1024x1024
            license="Apache-2.0",
            commercial=True,
            download_gb=38.6,
            reuse=((config.IMAGEGEN_MODELS_DIR, "boogu-{tag}"),),
        ),
    )
}


def resolve(keys: list[str] | None) -> list[ModelSpec]:
    if not keys or keys == ["all"]:
        return list(MODELS.values())
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        raise SystemExit(f"Unknown model(s) {unknown}; choose from {list(MODELS)}")
    return [MODELS[k] for k in keys]
