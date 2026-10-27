"""Known SenseNova checkpoints, 8-step LoRAs and the resolution buckets the models were trained on."""

from __future__ import annotations

from dataclasses import asdict, dataclass

# Trained buckets (examples/t2i/inference.py). Other sizes work but quality may drop.
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "1:1": (2048, 2048),
    "16:9": (2720, 1536),
    "9:16": (1536, 2720),
    "3:2": (2496, 1664),
    "2:3": (1664, 2496),
    "4:3": (2368, 1760),
    "3:4": (1760, 2368),
    "1:2": (1440, 2880),
    "2:1": (2880, 1440),
    "1:3": (1152, 3456),
    "3:1": (3456, 1152),
}


@dataclass(frozen=True)
class LoraSpec:
    repo: str
    filename: str


@dataclass(frozen=True)
class ModelSpec:
    id: str
    description: str
    infographic: bool = False  # tuned for infographics / dense text layouts
    fast_lora: LoraSpec | None = None  # 8-step distillation LoRA (cfg 1.0, 8 steps)


_U15_LORA = LoraSpec("sensenova/SenseNova-U1.5-8B-MoT-LoRAs", "SenseNova-U1.5-8B-MoT-LoRA-8step-V2.safetensors")
_U1_LORA = LoraSpec("sensenova/SenseNova-U1-8B-MoT-LoRAs", "SenseNova-U1-8B-MoT-LoRA-8step-V1.0.safetensors")
_U1_INFO_LORA = LoraSpec(
    "sensenova/SenseNova-U1-8B-MoT-LoRAs", "SenseNova-U1-8B-MoT-Infographic-LoRA-8step-V1.0.safetensors"
)

MODELS: dict[str, ModelSpec] = {
    s.id: s
    for s in (
        ModelSpec(
            "sensenova/SenseNova-U1.5-8B-MoT",
            "Flagship U1.5. Best text and layout rendering, native 4K, infographics and general T2I.",
            infographic=True,
            fast_lora=_U15_LORA,
        ),
        ModelSpec(
            "sensenova/SenseNova-U1.5-8B-MoT-SFT",
            "U1.5 SFT checkpoint (the 8-step LoRA was trained on this one).",
            infographic=True,
            fast_lora=_U15_LORA,
        ),
        ModelSpec(
            "sensenova/SenseNova-U1-8B-MoT-Infographic-V3",
            "U1 model specialised for infographic generation and editing.",
            infographic=True,
        ),
        ModelSpec(
            "sensenova/SenseNova-U1-8B-MoT-Infographic-V2",
            "Earlier U1 infographic model (dense small text).",
            infographic=True,
        ),
        ModelSpec(
            "sensenova/SenseNova-U1-8B-MoT-Infographic",
            "First U1 infographic model; has an 8-step LoRA.",
            infographic=True,
            fast_lora=_U1_INFO_LORA,
        ),
        ModelSpec("sensenova/SenseNova-U1-8B-MoT", "Original U1 base model.", fast_lora=_U1_LORA),
    )
}


def get(model_id: str) -> ModelSpec | None:
    spec = MODELS.get(model_id)
    if spec is None and "/" not in model_id:  # accept short names such as "SenseNova-U1.5-8B-MoT"
        spec = MODELS.get(f"sensenova/{model_id}")
    return spec


def as_dicts() -> list[dict]:
    return [asdict(s) for s in MODELS.values()]
