"""Catalog of every pretrained model AudioCraft supports."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str  # Hugging Face id, the canonical identifier used by API/MCP
    family: str  # musicgen | musicgen-style | audiogen | magnet | jasco
    kind: str  # music | sound
    params: str
    sample_rate: int
    channels: int
    capabilities: tuple[str, ...]
    vram_gb: float  # rough fp16 inference estimate (weights + activations), not a guarantee
    fixed_duration: float | None = None  # models that always produce a fixed length
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["capabilities"] = list(self.capabilities)
        return d


def _musicgen(name, params, vram, *, stereo=False, melody=False, notes=""):
    caps = ["text", "continuation", "unconditional", "mbd"] if not stereo else ["text", "continuation", "unconditional"]
    if melody:
        caps.append("melody")
    return ModelSpec(f"facebook/musicgen-{name}", "musicgen", "music", params,
                     32000, 2 if stereo else 1, tuple(caps), vram, notes=notes)


_SPECS: list[ModelSpec] = [
    _musicgen("small", "300M", 2.5),
    _musicgen("medium", "1.5B", 6),
    _musicgen("large", "3.3B", 10),
    _musicgen("melody", "1.5B", 6, melody=True),
    _musicgen("melody-large", "3.3B", 10, melody=True),
    _musicgen("stereo-small", "300M", 2.5, stereo=True),
    _musicgen("stereo-medium", "1.5B", 6, stereo=True),
    _musicgen("stereo-large", "3.3B", 10, stereo=True),
    _musicgen("stereo-melody", "1.5B", 6, stereo=True, melody=True),
    _musicgen("stereo-melody-large", "3.3B", 10, stereo=True, melody=True),
    ModelSpec("facebook/musicgen-style", "musicgen-style", "music", "1.5B", 32000, 1,
              ("text", "style", "continuation", "unconditional"), 6,
              notes="Text and/or audio-style conditioning."),
    ModelSpec("facebook/audiogen-medium", "audiogen", "sound", "1.5B", 16000, 1,
              ("text", "continuation", "unconditional"), 6, notes="Text to sound effects / ambience."),
]
for _n, _p, _v in (("small-10secs", "300M", 2.5), ("medium-10secs", "1.5B", 6),
                   ("small-30secs", "300M", 2.5), ("medium-30secs", "1.5B", 6)):
    _SPECS.append(ModelSpec(f"facebook/magnet-{_n}", "magnet", "music", _p, 32000, 1, ("text",), _v,
                            fixed_duration=10.0 if "10secs" in _n else 30.0,
                            notes="Non-autoregressive; fixed length."))
for _n, _p, _v in (("small", "300M", 2.5), ("medium", "1.5B", 6)):
    _SPECS.append(ModelSpec(f"facebook/audio-magnet-{_n}", "magnet", "sound", _p, 16000, 1, ("text",), _v,
                            fixed_duration=10.0, notes="Non-autoregressive text-to-sound; fixed 10 s."))
for _n, _p, _v, _mel in (("chords-drums-400M", "400M", 3, False), ("chords-drums-1B", "1B", 5, False),
                         ("chords-drums-melody-400M", "400M", 3, True), ("chords-drums-melody-1B", "1B", 5, True)):
    _caps = ("text", "chords", "drums") + (("melody",) if _mel else ())
    _SPECS.append(ModelSpec(f"facebook/jasco-{_n}", "jasco", "music", _p, 32000, 1, _caps, _v,
                            fixed_duration=10.0, notes="Flow matching; text + chords + drums" +
                            (" + melody." if _mel else ".")))

MODELS: dict[str, ModelSpec] = {s.id: s for s in _SPECS}

CODECS = {
    "facebook/encodec_24khz": {"sample_rate": 24000, "channels": 1, "bandwidths_kbps": [1.5, 3, 6, 12, 24]},
    "facebook/encodec_32khz": {"sample_rate": 32000, "channels": 1, "bandwidths_kbps": [None],
                               "notes": "MusicGen's codec: 4 codebooks @ 50 Hz"},
}
WATERMARK_MODELS = ["base"]
