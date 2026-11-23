"""The fixed prompt set (prompts.toml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tomllib

from . import config


@dataclass(frozen=True)
class Prompt:
    id: str
    category: str
    text: str
    check: str = ""


def load(path: Path | None = None, categories: list[str] | None = None, limit: int | None = None) -> list[Prompt]:
    """Prompts in file order, optionally filtered by category and cut to `limit` per category."""
    raw = tomllib.loads((path or config.PROMPTS_FILE).read_text(encoding="utf-8"))
    prompts = [Prompt(**p) for p in raw.get("prompt", [])]
    ids = [p.id for p in prompts]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate prompt ids: {dupes}")
    if categories:
        prompts = [p for p in prompts if p.category in categories]
    if limit:
        seen: dict[str, int] = {}
        kept = []
        for p in prompts:
            seen[p.category] = seen.get(p.category, 0) + 1
            if seen[p.category] <= limit:
                kept.append(p)
        prompts = kept
    return prompts
