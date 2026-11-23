"""imgeval: compare local text-to-image models on a fixed prompt set, then review them blind.

uv run imgeval list                                  # models, licenses, download size, weights ready?
uv run imgeval prepare boogu                         # download + quantize ahead of time
uv run imgeval run --name first                      # every model, every prompt, 2 seeds, 1024x1024
uv run imgeval run --name smoke --limit 1 --seeds 1  # one prompt per category, quick check
uv run imgeval report outputs/first                  # rebuild the review page
uv run imgeval tally outputs/first votes.json        # wins per model from the exported votes
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from . import config, prompts, report
from .models import MODELS, resolve, weights_ready

log = logging.getLogger("imgeval")


def _run_dir(arg: str) -> Path:
    p = Path(arg).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not (p / "run.json").exists():
        p = config.OUTPUT_DIR / arg
    if not (p / "run.json").exists():
        raise SystemExit(f"No run at {arg} (looked for run.json)")
    return p


def cmd_list(_args) -> None:
    for m in MODELS.values():
        ready = "ready" if weights_ready(m.weight_path()) else f"not downloaded (~{m.download_gb:.0f} GB)"
        print(f"{m.key:12} {m.label:30} {m.steps:>2} steps  {m.license:40} {ready}")


def cmd_prepare(args) -> None:
    from . import prepare

    for spec in resolve(args.models):
        print(f"{spec.key}: {prepare.ensure_weights(spec)}")


def new_settings(args) -> dict:
    chosen = prompts.load(categories=args.category, limit=args.limit)
    if not chosen:
        raise SystemExit("No prompts match the filters")
    side = args.size // 16 * 16
    return {
        "name": args.name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": [m.key for m in resolve(args.models)],
        "prompt_ids": [p.id for p in chosen],
        "seeds": [args.seed_base + i for i in range(args.seeds)],
        "width": side,
        "height": side,
        "quantize": config.QUANTIZE,
    }


def cmd_run(args) -> None:
    run_dir = config.OUTPUT_DIR / args.name
    settings_file = run_dir / "run.json"
    if settings_file.exists():
        # Resuming: keep the original prompts, seeds and size so every model sees the same inputs.
        settings = json.loads(settings_file.read_text())
        added = [m.key for m in resolve(args.models) if m.key not in settings["models"]] if args.models else []
        settings["models"] += added
        n_prompts, n_seeds = len(settings["prompt_ids"]), len(settings["seeds"])
        log.warning("Resuming run %s (%d prompts x %d seeds)", args.name, n_prompts, n_seeds)
    else:
        settings = new_settings(args)
        run_dir.mkdir(parents=True)
    settings_file.write_text(json.dumps(settings, indent=2))

    keys = [m.key for m in resolve(args.models)] if args.models else settings["models"]
    failed = []
    for key in keys:
        # One process per model, so each model's memory is fully returned before the next loads.
        code = subprocess.call([sys.executable, "-m", "imgeval.worker", str(run_dir), key])
        if code:
            failed.append(key)
            log.warning("%s failed (exit %d); continuing with the other models", key, code)
    page = report.build(run_dir)
    print(f"Review page: {page}")
    if failed:
        raise SystemExit(f"Failed: {failed}. Re-run the same command to retry; finished images are kept.")


def cmd_report(args) -> None:
    print(report.build(_run_dir(args.run)))


def cmd_tally(args) -> None:
    run_dir = _run_dir(args.run)
    votes = Path(args.votes).expanduser().resolve() if args.votes else None
    print(report.format_tally(report.tally(run_dir, votes)))


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Models under test and whether their weights are ready").set_defaults(fn=cmd_list)

    p = sub.add_parser("prepare", help="Download and quantize weights ahead of a run")
    p.add_argument("models", nargs="*", help=f"Default: all ({', '.join(MODELS)})")
    p.set_defaults(fn=cmd_prepare)

    p = sub.add_parser("run", help="Generate images (resumable) and build the review page")
    p.add_argument("--name", default=time.strftime("run-%Y%m%d-%H%M"), help="Run folder under outputs/")
    p.add_argument("--models", nargs="+", help=f"Default: all ({', '.join(MODELS)})")
    p.add_argument("--category", nargs="+", help="Only these prompt categories")
    p.add_argument("--limit", type=int, help="At most this many prompts per category")
    p.add_argument("--seeds", type=int, default=2, help="Seeds per prompt (default 2)")
    p.add_argument("--seed-base", type=int, default=1001)
    p.add_argument("--size", type=int, default=1024, help="Square image side in px (default 1024)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("report", help="Rebuild the blind review page for a run")
    p.add_argument("run", help="Run name or folder")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("tally", help="Wins per model from exported votes")
    p.add_argument("run", help="Run name or folder")
    p.add_argument("votes", nargs="?", help="votes.json exported from the page (default: <run>/votes.json)")
    p.set_defaults(fn=cmd_tally)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
