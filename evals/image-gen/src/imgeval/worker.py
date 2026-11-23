"""Generate every (prompt, seed) of a run with one model. Started as its own process per model by `imgeval run`.

A fresh process per model returns all of its memory to the system before the next model loads, which matters on
a 48 GB machine where the larger models peak near 30 GB. Images that already exist are skipped, so an interrupted
run resumes where it stopped.

    python -m imgeval.worker <run_dir> <model_key>
"""

from __future__ import annotations

import gc
import json
import logging
import sys
import time
from pathlib import Path

from . import config, prompts
from .models import MODELS, ModelSpec

log = logging.getLogger("imgeval")


def _load_model(spec: ModelSpec):
    import mlx.core as mx

    from . import prepare

    path = prepare.ensure_weights(spec)
    if config.MLX_CACHE_LIMIT_GB > 0:
        mx.set_cache_limit(int(config.MLX_CACHE_LIMIT_GB * 1024**3))
    # Timed here, after any first-use download, so load_s is the load alone.
    t0 = time.perf_counter()
    # The saved copy already carries its quantization, so quantize is not passed again.
    model = spec.model_class()(model_path=str(path), model_config=spec.model_config())
    return model, path, round(time.perf_counter() - t0, 1)


def _free_mlx() -> None:
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except ImportError:
        pass


def _peak_gb() -> float | None:
    try:
        import mlx.core as mx

        return round(mx.get_peak_memory() / 1024**3, 1)
    except ImportError:
        return None


def image_path(run_dir: Path, key: str, prompt_id: str, seed: int) -> Path:
    return run_dir / "images" / key / f"{prompt_id}-s{seed}.png"


def run_model(spec: ModelSpec, run_dir: Path) -> dict | None:
    """Fill in the missing images for one model and write its timing + memory summary. Returns the summary."""
    settings = json.loads((run_dir / "run.json").read_text())
    wanted = set(settings["prompt_ids"])
    todo = [
        (p, s)
        for p in prompts.load()
        if p.id in wanted
        for s in settings["seeds"]
        if not image_path(run_dir, spec.key, p.id, s).exists()
    ]
    if not todo:
        log.warning("%s: all images already present", spec.key)
        return None

    (run_dir / "images" / spec.key).mkdir(parents=True, exist_ok=True)
    (run_dir / "results").mkdir(exist_ok=True)
    model, path, load_s = _load_model(spec)
    log.warning("%s: loaded in %.0fs, %d images to make", spec.key, load_s, len(todo))

    with open(run_dir / "results" / f"{spec.key}.jsonl", "a", encoding="utf-8") as results:
        for i, (p, seed) in enumerate(todo, 1):
            t = time.perf_counter()
            img = model.generate_image(
                seed=seed,
                prompt=p.text,
                num_inference_steps=spec.steps,
                width=settings["width"],
                height=settings["height"],
            )
            seconds = round(time.perf_counter() - t, 2)
            out = image_path(run_dir, spec.key, p.id, seed)
            # Write beside the target and rename, so a crash never leaves a half image that resume would skip.
            partial = out.with_name(out.stem + ".partial.png")
            img.save(path=partial, overwrite=True)
            partial.rename(out)
            results.write(json.dumps({"prompt_id": p.id, "seed": seed, "seconds": seconds}) + "\n")
            results.flush()
            log.warning("%s: [%d/%d] %s s%d %.1fs", spec.key, i, len(todo), p.id, seed, seconds)
            _free_mlx()

    summary = {
        "model": spec.key,
        "label": spec.label,
        "repo": spec.repo,
        "revision": spec.revision,
        "steps": spec.steps,
        "quantize": config.QUANTIZE,
        "weights": str(path),
        "load_s": load_s,
        "peak_gb": _peak_gb(),
        "license": spec.license,
        "commercial": spec.commercial,
    }
    (run_dir / "results" / f"{spec.key}.meta.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_dir, key = (argv or sys.argv[1:])[:2]
    run_model(MODELS[key], Path(run_dir))


if __name__ == "__main__":
    main()
