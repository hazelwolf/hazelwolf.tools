"""Blind side-by-side review page for a run, and the vote tally.

`build` writes <run_dir>/index.html. Each (prompt, seed) shows every model's image under a letter, in an order
shuffled per comparison (seeded, so rebuilding keeps the order), so the reviewer cannot tell which model is which.
Votes stay in the browser and are exported as votes.json; `tally` turns that file into wins per model.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from . import prompts
from .models import MODELS
from .worker import image_path

TIE, BAD = "tie", "bad"


def _times(run_dir: Path, key: str) -> list[float]:
    f = run_dir / "results" / f"{key}.jsonl"
    if not f.exists():
        return []
    return [json.loads(line)["seconds"] for line in f.read_text().splitlines() if line.strip()]


def model_stats(run_dir: Path, keys: list[str]) -> list[dict]:
    rows = []
    for key in keys:
        meta_file = run_dir / "results" / f"{key}.meta.json"
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        times = _times(run_dir, key)
        # The first image after a load includes MLX warm-up; the median is not skewed by it.
        spec = MODELS[key]
        rows.append(
            {
                "model": key,
                "label": spec.label,
                "steps": spec.steps,
                "license": spec.license,
                "commercial": spec.commercial,
                "images": len(times),
                "median_s": round(statistics.median(times), 1) if times else None,
                "load_s": meta.get("load_s"),
                "peak_gb": meta.get("peak_gb"),
            }
        )
    return rows


def comparisons(run_dir: Path, settings: dict) -> list[dict]:
    wanted = set(settings["prompt_ids"])
    out = []
    for p in prompts.load():
        if p.id not in wanted:
            continue
        for seed in settings["seeds"]:
            keys = [k for k in settings["models"] if image_path(run_dir, k, p.id, seed).exists()]
            if len(keys) < 2:
                continue
            random.Random(f"{settings['name']}:{p.id}:{seed}").shuffle(keys)
            out.append(
                {
                    "id": f"{p.id}|{seed}",
                    "prompt_id": p.id,
                    "category": p.category,
                    "text": p.text,
                    "check": p.check,
                    "seed": seed,
                    "images": [
                        {"model": k, "src": image_path(run_dir, k, p.id, seed).relative_to(run_dir).as_posix()}
                        for k in keys
                    ],
                }
            )
    return out


def _settings(run_dir: Path) -> dict:
    settings = json.loads((run_dir / "run.json").read_text())
    # Older runs may name models since dropped from MODELS; leave them out of the page and the tally.
    settings["models"] = [k for k in settings["models"] if k in MODELS]
    return settings


def build(run_dir: Path) -> Path:
    settings = _settings(run_dir)
    data = {
        "run": settings["name"],
        "settings": {k: settings[k] for k in ("width", "height", "quantize", "seeds")},
        "stats": model_stats(run_dir, settings["models"]),
        "items": comparisons(run_dir, settings),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = run_dir / "index.html"
    page = (Path(__file__).parent / "review.html").read_text(encoding="utf-8")
    out.write_text(page.replace("__DATA__", payload), encoding="utf-8")
    return out


def tally(run_dir: Path, votes_file: Path | None = None) -> dict:
    """Wins per model overall and per category, from an exported votes.json."""
    settings = _settings(run_dir)
    votes = json.loads((votes_file or run_dir / "votes.json").read_text())["votes"]
    category = {c["id"]: c["category"] for c in comparisons(run_dir, settings)}
    keys = [*settings["models"], TIE, BAD]
    overall = dict.fromkeys(keys, 0)
    by_cat: dict[str, dict[str, int]] = {}
    for item_id, choice in votes.items():
        if item_id not in category or choice not in overall:
            continue
        overall[choice] += 1
        by_cat.setdefault(category[item_id], dict.fromkeys(keys, 0))[choice] += 1
    return {"votes": sum(overall.values()), "of": len(category), "overall": overall, "by_category": by_cat}


def format_tally(t: dict) -> str:
    keys = list(t["overall"])
    cats = sorted(t["by_category"])
    head = ["model", "total", *cats]
    rows = [[k, str(t["overall"][k]), *(str(t["by_category"][c][k]) for c in cats)] for k in keys]
    widths = [max(len(r[i]) for r in [head, *rows]) for i in range(len(head))]
    lines = ["  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in [head, *rows]]
    return "\n".join([f"{t['votes']} of {t['of']} comparisons voted", *lines])
