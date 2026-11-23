"""Runner, resume, review page and tally, with fake models (no weights, GPU or network)."""

from __future__ import annotations

import dataclasses
import json
import re

import pytest
from imgeval import cli, config, prompts, report, worker
from imgeval.models import MODELS
from PIL import Image


class FakeImage:
    def save(self, path, overwrite=False):
        Image.new("RGB", (8, 8)).save(path)


class FakeModel:
    def __init__(self, calls):
        self.calls = calls

    def generate_image(self, seed, prompt, num_inference_steps, width, height):
        self.calls.append((seed, prompt, num_inference_steps, width, height))
        return FakeImage()


@pytest.fixture
def env(monkeypatch, tmp_path):
    calls: dict[str, list] = {}

    def fake_load(spec):
        calls.setdefault(spec.key, [])
        return FakeModel(calls[spec.key]), tmp_path / spec.key, 0.1

    def in_process(cmd):
        # cmd is [python, -m, imgeval.worker, run_dir, key]; run it here instead of in a subprocess.
        worker.main(cmd[-2:])
        return 0

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(worker, "_load_model", fake_load)
    monkeypatch.setattr(cli.subprocess, "call", in_process)
    return calls, tmp_path


def test_prompt_set_is_well_formed():
    ps = prompts.load()
    assert len(ps) == 40 and len({p.id for p in ps}) == 40
    assert {p.category for p in ps} == {"photo", "text", "composition", "style", "people"}
    assert all(p.text.strip() for p in ps)


def test_limit_and_category_filters():
    assert len(prompts.load(limit=1)) == 5
    assert {p.category for p in prompts.load(categories=["text"])} == {"text"}


def test_run_generates_every_model_with_its_own_steps(env):
    calls, out = env
    cli.main(["run", "--name", "t", "--limit", "1", "--seeds", "2", "--size", "1000"])
    run = out / "t"
    for key, spec in MODELS.items():
        assert len(calls[key]) == 10  # 5 prompts x 2 seeds
        assert {c[2] for c in calls[key]} == {spec.steps}
        assert {(c[3], c[4]) for c in calls[key]} == {(992, 992)}  # rounded down to a multiple of 16
        assert len(list((run / "images" / key).glob("*.png"))) == 10
        assert not list((run / "images" / key).glob("*.partial.png"))
    # Same seeds and prompts for every model, so the comparison is like for like.
    assert len({tuple(sorted((c[0], c[1]) for c in v)) for v in calls.values()}) == 1
    assert (run / "index.html").exists()


def test_resume_skips_finished_images_and_keeps_settings(env):
    calls, out = env
    cli.main(["run", "--name", "t", "--models", "zimage", "--limit", "1", "--seeds", "1"])
    (out / "t" / "images" / "zimage" / "photo-01-s1001.png").unlink()
    calls.clear()
    # Different flags on resume are ignored: the run keeps its original prompts and seeds.
    cli.main(["run", "--name", "t", "--models", "zimage", "--seeds", "3"])
    assert [(c[0], c[1][:10]) for c in calls["zimage"]] == [(1001, "A red fox ")]


def test_resume_can_add_a_model(env):
    calls, out = env
    cli.main(["run", "--name", "t", "--models", "zimage", "--limit", "1", "--seeds", "1"])
    cli.main(["run", "--name", "t", "--models", "boogu"])
    settings = json.loads((out / "t" / "run.json").read_text())
    assert settings["models"] == ["zimage", "boogu"]
    assert len(calls["boogu"]) == 5


def test_review_page_is_blind_and_stable(env):
    _, out = env
    cli.main(["run", "--name", "t", "--limit", "2", "--seeds", "1"])
    run = out / "t"
    items = report.comparisons(run, json.loads((run / "run.json").read_text()))
    assert len(items) == 10 and all(len(i["images"]) == len(MODELS) for i in items)
    orders = [tuple(im["model"] for im in i["images"]) for i in items]
    assert len(set(orders)) > 1  # shuffled per comparison, not one fixed order
    html = report.build(run).read_text()
    assert html == report.build(run).read_text()  # rebuilding keeps the same order
    data = json.loads(re.search(r"const DATA = (.*);\n", html).group(1))
    assert data["items"][0]["images"][0]["src"].startswith("images/")
    # Model names are not shown next to images; labels appear only in the stats table.
    assert all("label" not in im for i in data["items"] for im in i["images"])


def test_tally_counts_wins_per_model_and_category(env):
    _, out = env
    cli.main(["run", "--name", "t", "--models", "zimage", "boogu", "--category", "text", "photo", "--limit", "1"])
    run = out / "t"
    votes = {"text-01|1001": "zimage", "text-01|1002": "boogu", "photo-01|1001": "zimage", "photo-01|1002": "tie"}
    (run / "votes.json").write_text(json.dumps({"run": "t", "votes": {**votes, "gone|1": "zimage"}}))
    t = report.tally(run)
    assert t["votes"] == 4 and t["of"] == 4
    assert t["overall"] == {"zimage": 2, "boogu": 1, "tie": 1, "bad": 0}
    assert t["by_category"]["photo"]["zimage"] == 1
    assert "4 of 4 comparisons voted" in report.format_tally(t)


def test_baseline_reuses_zimage_copy(monkeypatch, tmp_path):
    zimage_dir = tmp_path / "zimage-models"
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "eval-models")
    spec = dataclasses.replace(MODELS["zimage"], reuse=((zimage_dir, "z-image-turbo-{tag}"),))
    assert spec.weight_path(8) == tmp_path / "eval-models" / "zimage-q8"
    (zimage_dir / "z-image-turbo-q8" / "transformer").mkdir(parents=True)
    assert spec.weight_path(8) == zimage_dir / "z-image-turbo-q8"
