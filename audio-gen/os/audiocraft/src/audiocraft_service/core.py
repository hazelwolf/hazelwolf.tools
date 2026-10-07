"""AudioCraft inference engine. The HTTP API and the MCP server are thin wrappers over this module."""
from __future__ import annotations

import gc
import inspect
import threading
import time
from collections import OrderedDict
from collections.abc import Callable

import torch

from . import (
    audio_io,
    config,
)
from .errors import ServiceError
from .registry import CODECS, MODELS, WATERMARK_MODELS, ModelSpec
from .schemas import (
    CodecReconstructRequest,
    ContinuationRequest,
    GenerateRequest,
    GenerationResult,
    JascoRequest,
    MbdRegenerateRequest,
    MelodyRequest,
    SamplingParams,
    UnconditionalRequest,
    WatermarkDetectRequest,
    WatermarkEmbedRequest,
)

_JASCO_EXTRA = {"euler", "euler_steps"}
_ENCODEC24_NQ = {1.5: 2, 3.0: 4, 6.0: 8, 12.0: 16, 24.0: 32}


class _TorchTrusted:
    """Proxy for `torch` inside audiocraft.models.loaders: torch>=2.6 defaults torch.load to weights_only=True,
    which breaks upstream's omegaconf-pickled Meta checkpoints. Only used for AudioCraft's own loaders
    (checkpoints fetched from Meta's Hugging Face repos); user-supplied files are loaded elsewhere with
    weights_only=True."""

    def __getattr__(self, name):
        return getattr(torch, name)

    @staticmethod
    def load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return torch.load(*args, **kwargs)


def _patch_upstream_loaders():
    from audiocraft.models import loaders
    if not isinstance(loaders.torch, _TorchTrusted):
        loaders.torch = _TorchTrusted()


def device() -> str:
    return config.DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")


class _LRU:
    def __init__(self, size: int):
        self.size, self._d = max(1, size), OrderedDict()

    def get(self, key, loader: Callable):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        while len(self._d) >= self.size:
            self._d.popitem(last=False)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._d[key] = loader()
        return self._d[key]

    def keys(self):
        return list(self._d)

    def clear(self):
        self._d.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


_gen_models = _LRU(config.MAX_LOADED_MODELS)  # big LMs
_aux_models = _LRU(2)  # codecs, MBD, Demucs, AudioSeal
_gpu_lock = threading.RLock()  # one inference at a time on the GPU


# --------------------------------------------------------------------------- helpers
def get_spec(model_id: str) -> ModelSpec:
    spec = MODELS.get(model_id)
    if spec is None:  # accept short names such as "musicgen-small"
        spec = MODELS.get(f"facebook/{model_id}")
    if spec is None:
        raise ServiceError(f"Unknown model '{model_id}'. See GET /v1/models.", 404)
    return spec


def _load_gen_model(spec: ModelSpec):
    from audiocraft.models import JASCO, AudioGen, MAGNeT, MusicGen

    from . import config as c

    dev = device()
    if spec.family in ("musicgen", "musicgen-style"):
        return MusicGen.get_pretrained(spec.id, device=dev)
    if spec.family == "audiogen":
        return AudioGen.get_pretrained(spec.id, device=dev)
    if spec.family == "magnet":
        return MAGNeT.get_pretrained(spec.id, device=dev)
    if spec.family == "jasco":
        mapping = c.UPSTREAM_DIR / "assets" / "chord_to_index_mapping.pkl"
        return JASCO.get_pretrained(spec.id, device=dev, chords_mapping_path=str(mapping))
    raise ServiceError(f"Unsupported family {spec.family}", 500)


def _gen(spec: ModelSpec):
    _patch_upstream_loaders()
    return _gen_models.get(spec.id, lambda: _load_gen_model(spec))


def _seed(seed: int | None):
    if seed is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def _require(spec: ModelSpec, cap: str, what: str):
    if cap not in spec.capabilities:
        ok = [m.id for m in MODELS.values() if cap in m.capabilities]
        raise ServiceError(f"{spec.id} does not support {what}. Models that do: {', '.join(ok)}", 422)


def _apply_params(model, spec: ModelSpec, p: SamplingParams, warnings: list[str]) -> float:
    """Reset + apply generation params. Returns the effective duration in seconds."""
    sig = inspect.signature(model.set_generation_params)
    var_kw = any(x.kind is inspect.Parameter.VAR_KEYWORD for x in sig.parameters.values())
    given = p.model_dump(exclude_none=True)
    duration = given.pop("duration", None)
    kwargs = {}
    for k, v in given.items():
        if k in sig.parameters and sig.parameters[k].kind is not inspect.Parameter.VAR_KEYWORD:
            kwargs[k] = v
        elif var_kw and k in _JASCO_EXTRA:
            kwargs[k] = v
        else:
            raise ServiceError(f"Parameter '{k}' is not supported by {spec.id} ({spec.family}).", 422)
    if duration is not None:
        if spec.fixed_duration:
            warnings.append(f"duration ignored: {spec.id} always generates {spec.fixed_duration:g}s")
        else:
            if duration > config.MAX_DURATION:
                raise ServiceError(f"duration {duration}s exceeds AUDIOCRAFT_MAX_DURATION={config.MAX_DURATION:g}", 422)
            kwargs["duration"] = duration
    try:
        model.set_generation_params(**kwargs)
    except AssertionError as e:
        raise ServiceError(f"Invalid generation params: {e}", 422) from None
    return float(spec.fixed_duration or getattr(model, "duration", 0))


def _check_batch(prompts):
    if len(prompts) > config.MAX_BATCH:
        raise ServiceError(f"At most {config.MAX_BATCH} prompts per request (AUDIOCRAFT_MAX_BATCH).", 422)


def _mbd_decode(model, tokens):
    mbd = _aux_models.get(("mbd", "musicgen"), _load_mbd_musicgen)
    return mbd.tokens_to_wav(tokens)


def _load_mbd_musicgen():
    _patch_upstream_loaders()
    from audiocraft.models import MultiBandDiffusion
    return MultiBandDiffusion.get_mbd_musicgen(device=device())


def _guard(fn):
    """Run fn on the GPU lock; map CUDA OOM to a clear error."""
    with _gpu_lock:
        try:
            return fn()
        except torch.OutOfMemoryError:
            _gen_models.clear()
            _aux_models.clear()
            raise ServiceError("CUDA out of memory. Try a smaller model, shorter duration or fewer prompts "
                               "(see GET /v1/models for approximate VRAM needs).", 507) from None


def _finish(spec_id: str, wav, sr: int, prompts, req, warnings, t0, seed, extra=None) -> GenerationResult:
    files = []
    for i in range(wav.shape[0]):
        stem = audio_io.new_stem(spec_id, i)
        prompt = prompts[i] if prompts and i < len(prompts) else None
        files.append(audio_io.save_audio(wav[i], sr, stem, req.output, prompt))
    return GenerationResult(model=spec_id, sample_rate=sr, channels=wav.shape[1],
                            duration_s=round(wav.shape[-1] / sr, 3), elapsed_s=round(time.time() - t0, 2),
                            seed=seed, files=files, warnings=warnings, extra=extra or {})


# --------------------------------------------------------------------------- catalog / status
def list_models() -> dict:
    return {
        "generative": [m.to_dict() for m in MODELS.values()],
        "codecs": CODECS,
        "multi_band_diffusion": {"bandwidths_kbps": [1.5, 3.0, 6.0], "musicgen_decoder": True},
        "watermark": {"models": WATERMARK_MODELS, "nbits": 16, "sample_rate": 16000},
        "device": device(),
    }


def status() -> dict:
    info = {"device": device(), "loaded_models": _gen_models.keys(), "loaded_aux": [str(k) for k in _aux_models.keys()],
            "models_dir": str(config.MODELS_DIR), "output_dir": str(config.OUTPUT_DIR)}
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        info.update(gpu=torch.cuda.get_device_name(0), vram_free_gb=round(free / 1e9, 2),
                    vram_total_gb=round(total / 1e9, 2))
    return info


def unload_all() -> dict:
    with _gpu_lock:
        _gen_models.clear()
        _aux_models.clear()
    return status()


# --------------------------------------------------------------------------- generation
def generate(req: GenerateRequest) -> GenerationResult:
    spec = get_spec(req.model)
    _check_batch(req.prompts)
    if req.use_mbd:
        _require(spec, "mbd", "Multi-Band Diffusion decoding")

    def run():
        t0, warnings = time.time(), []
        model = _gen(spec)
        _apply_params(model, spec, req.params, warnings)
        _seed(req.seed)
        if req.use_mbd:
            wav, tokens = model.generate(req.prompts, return_tokens=True)
            wav = _mbd_decode(model, tokens)
        else:
            wav = model.generate(req.prompts)
        return _finish(spec.id, wav, int(model.sample_rate if not req.use_mbd else 32000), req.prompts, req,
                       warnings, t0, req.seed)

    return _guard(run)


def generate_unconditional(req: UnconditionalRequest) -> GenerationResult:
    spec = get_spec(req.model)
    _require(spec, "unconditional", "unconditional generation")
    if req.num_samples > config.MAX_BATCH:
        raise ServiceError(f"At most {config.MAX_BATCH} samples per request.", 422)

    def run():
        t0, warnings = time.time(), []
        model = _gen(spec)
        _apply_params(model, spec, req.params, warnings)
        _seed(req.seed)
        wav = model.generate_unconditional(req.num_samples)
        return _finish(spec.id, wav, int(model.sample_rate), None, req, warnings, t0, req.seed)

    return _guard(run)


def generate_with_melody(req: MelodyRequest) -> GenerationResult:
    spec = get_spec(req.model)
    if "melody" not in spec.capabilities and "style" not in spec.capabilities:
        raise ServiceError(f"{spec.id} takes no melody/style audio. "
                           "Use a *-melody* model or facebook/musicgen-style.", 422)
    if req.use_mbd:
        _require(spec, "mbd", "Multi-Band Diffusion decoding")
    _check_batch(req.prompts)
    style_given = any(v is not None for v in (req.style_eval_q, req.style_excerpt_length, req.style_ds_factor))
    if style_given and spec.family != "musicgen-style":
        raise ServiceError("style_* parameters only apply to facebook/musicgen-style.", 422)
    mel, mel_sr = audio_io.load_audio(req.melody, config.MAX_INPUT_SECONDS)

    def run():
        t0, warnings = time.time(), []
        model = _gen(spec)
        _apply_params(model, spec, req.params, warnings)
        if spec.family == "musicgen-style":
            kw = {k: v for k, v in (("eval_q", req.style_eval_q), ("excerpt_length", req.style_excerpt_length),
                                    ("ds_factor", req.style_ds_factor)) if v is not None}
            model.set_style_conditioner_params(**({"eval_q": 3, "excerpt_length": 3.0} | kw))
        _seed(req.seed)
        melodies = mel[None].expand(len(req.prompts), -1, -1)
        wav, tokens = model.generate_with_chroma(req.prompts, melodies, mel_sr, return_tokens=True)
        if req.use_mbd:
            wav = _mbd_decode(model, tokens)
        return _finish(spec.id, wav, int(model.sample_rate), req.prompts, req, warnings, t0, req.seed)

    return _guard(run)


def continue_audio(req: ContinuationRequest) -> GenerationResult:
    spec = get_spec(req.model)
    _require(spec, "continuation", "audio continuation")
    if req.use_mbd:
        _require(spec, "mbd", "Multi-Band Diffusion decoding")
    prompts = req.prompts
    if prompts:
        _check_batch(prompts)
    audio, sr = audio_io.load_audio(req.audio, req.prompt_duration or config.MAX_INPUT_SECONDS)
    prompt_s = audio.shape[-1] / sr

    def run():
        t0, warnings = time.time(), []
        model = _gen(spec)
        total = _apply_params(model, spec, req.params, warnings)
        if prompt_s >= total:
            raise ServiceError(f"Audio prompt ({prompt_s:.1f}s) must be shorter than duration ({total:g}s). "
                               "Set params.duration larger or prompt_duration smaller.", 422)
        _seed(req.seed)
        n = len(prompts) if prompts else 1
        batch = audio[None].expand(n, -1, -1)
        wav, tokens = model.generate_continuation(batch, sr, prompts, return_tokens=True)
        if req.use_mbd:
            wav = _mbd_decode(model, tokens)
        return _finish(spec.id, wav, int(model.sample_rate), prompts, req, warnings, t0, req.seed,
                       {"prompt_seconds": round(prompt_s, 2)})

    return _guard(run)


def _drums_from_mix(wav: torch.Tensor, sr: int) -> torch.Tensor:
    from demucs import pretrained
    from demucs.apply import apply_model
    from demucs.audio import convert_audio

    dev = device()
    dm = _aux_models.get(("demucs", "htdemucs"), lambda: pretrained.get_model("htdemucs").to(dev))
    x = convert_audio(wav, sr, dm.samplerate, dm.audio_channels)
    with torch.no_grad():
        stems = apply_model(dm, x.to(dev).unsqueeze(0), device=dev).squeeze(0)
    drums = stems[dm.sources.index("drums")].cpu()
    return convert_audio(drums, dm.samplerate, sr, 1)


def generate_jasco(req: JascoRequest) -> GenerationResult:
    spec = get_spec(req.model)
    if spec.family != "jasco":
        raise ServiceError(f"{spec.id} is not a JASCO model.", 422)
    _check_batch(req.prompts)
    if req.drums and req.drums_from_mix:
        raise ServiceError("Provide either `drums` or `drums_from_mix`, not both.", 422)
    if req.melody_salience:
        _require(spec, "melody", "melody conditioning")

    drums = drums_sr = None
    if req.drums:
        drums, drums_sr = audio_io.load_audio(req.drums, 10.0)
    elif req.drums_from_mix:
        mix, mix_sr = audio_io.load_audio(req.drums_from_mix, 10.0)
        drums, drums_sr = mix, mix_sr  # separated under the GPU lock below
    salience = None
    if req.melody_salience:
        path = audio_io.resolve_path(req.melody_salience)
        try:
            salience = torch.load(path, weights_only=True, map_location="cpu").float()
        except Exception as e:  # noqa: BLE001
            raise ServiceError(f"melody_salience must be a torch tensor file: {e}", 400) from None
        if salience.dim() != 2 or 53 not in salience.shape:
            raise ServiceError(f"melody_salience must be 2-D with a 53-bin axis, got {tuple(salience.shape)}", 422)
        if salience.shape[0] != 53:
            salience = salience.permute(1, 0)

    def run():
        t0, warnings = time.time(), []
        model = _gen(spec)
        chords = None
        if req.chords:
            unknown = sorted({c.chord for c in req.chords if c.chord not in model.chords_mapping})
            if unknown:
                raise ServiceError(f"Unsupported chord label(s): {unknown}. JASCO knows {len(model.chords_mapping)} "
                                   "labels, e.g. C, Dm7, G7, Am, F, Bb, N (no chord).", 422)
            chords = [(c.chord, c.start) for c in req.chords]
        d = drums
        if req.drums_from_mix:
            d = _drums_from_mix(drums, drums_sr)
        _apply_params(model, spec, req.params, warnings)
        _seed(req.seed)
        wav = model.generate_music(descriptions=req.prompts, chords=chords, drums_wav=d,
                                   drums_sample_rate=drums_sr or 32000, melody_salience_matrix=salience)
        return _finish(spec.id, wav, int(model.compression_model.sample_rate), req.prompts, req, warnings, t0, req.seed)

    return _guard(run)


# --------------------------------------------------------------------------- codecs / MBD / watermark
def codec_reconstruct(req: CodecReconstructRequest) -> GenerationResult:
    from audiocraft.data.audio_utils import convert_audio
    from audiocraft.models import CompressionModel

    if req.model.endswith("24khz") is False and req.bandwidth_kbps is not None:
        raise ServiceError("bandwidth_kbps only applies to facebook/encodec_24khz.", 422)
    wav, sr = audio_io.load_audio(req.audio, config.MAX_INPUT_SECONDS)

    def run():
        t0 = time.time()
        _patch_upstream_loaders()
        codec = _aux_models.get(("codec", req.model),
                                lambda: CompressionModel.get_pretrained(req.model, device=device()))
        if req.model.endswith("24khz"):
            bw = req.bandwidth_kbps or 6.0
            if bw not in _ENCODEC24_NQ:
                raise ServiceError(f"bandwidth_kbps must be one of {sorted(_ENCODEC24_NQ)}", 422)
            codec.set_num_codebooks(_ENCODEC24_NQ[bw])
        x = convert_audio(wav, sr, codec.sample_rate, codec.channels)[None].to(device())
        with torch.no_grad():
            codes, scale = codec.encode(x)
            out = codec.decode(codes, scale)
        extra = {"codes_shape": list(codes.shape), "num_codebooks": int(codes.shape[1]),
                 "frame_rate": float(codec.frame_rate), "input_seconds": round(wav.shape[-1] / sr, 2)}
        return _finish(req.model, out, int(codec.sample_rate), None, req, [], t0, None, extra)

    return _guard(run)


def mbd_regenerate(req: MbdRegenerateRequest) -> GenerationResult:
    from audiocraft.data.audio_utils import convert_audio
    from audiocraft.models import MultiBandDiffusion

    wav, sr = audio_io.load_audio(req.audio, 60.0)

    def run():
        t0 = time.time()
        _patch_upstream_loaders()
        mbd = _aux_models.get(("mbd24", req.bandwidth_kbps),
                              lambda: MultiBandDiffusion.get_mbd_24khz(bw=req.bandwidth_kbps, device=device()))
        x = convert_audio(wav, sr, mbd.sample_rate, 1)[None].to(device())
        with torch.no_grad():
            out = mbd.regenerate(x, mbd.sample_rate)
        return _finish("mbd-24khz", out, int(mbd.sample_rate), None, req, [], t0, None,
                       {"bandwidth_kbps": req.bandwidth_kbps})

    return _guard(run)


def _audioseal():
    from audiocraft.models.watermark import AudioSeal
    _patch_upstream_loaders()
    return _aux_models.get(("audioseal", "base"), lambda: AudioSeal.get_pretrained("base", device=device()))


def watermark_embed(req: WatermarkEmbedRequest) -> GenerationResult:
    from audiocraft.data.audio_utils import convert_audio

    wav, sr = audio_io.load_audio(req.audio, config.MAX_INPUT_SECONDS)

    def run():
        t0 = time.time()
        wm = _audioseal()
        x = convert_audio(wav, sr, 16000, 1)[None].to(device())
        msg = None
        if req.message_bits:
            msg = torch.tensor([[int(b) for b in req.message_bits]], dtype=torch.int32, device=device())
        with torch.no_grad():
            out = wm.get_watermark(x, message=msg, sample_rate=16000) * req.alpha + x
        return _finish("audioseal", out, 16000, None, req, [], t0, None,
                       {"message_bits": req.message_bits, "alpha": req.alpha})

    return _guard(run)


def watermark_detect(req: WatermarkDetectRequest) -> dict:
    from audiocraft.data.audio_utils import convert_audio

    wav, sr = audio_io.load_audio(req.audio, config.MAX_INPUT_SECONDS)

    def run():
        wm = _audioseal()
        x = convert_audio(wav, sr, 16000, 1)[None].to(device())
        with torch.no_grad():
            res = wm.detect_watermark(x)  # (1, 2+nbits, T)
        prob = res[0, 1]  # per-frame probability of being watermarked
        detected = prob > req.threshold
        bits = None
        if detected.any():
            bits = "".join("1" if v > 0.5 else "0" for v in res[0, 2:, detected].float().mean(dim=-1).tolist())
        return {"watermarked": bool(prob.mean() > req.threshold), "probability": round(float(prob.mean()), 4),
                "frames_detected_fraction": round(float(detected.float().mean()), 4), "message_bits": bits,
                "seconds": round(x.shape[-1] / 16000, 2)}

    return _guard(run)
