"""First-use weight preparation, with the download and quantization mocked."""

from __future__ import annotations

import pytest
from zimage_service import config, core, prepare


@pytest.fixture
def env(monkeypatch, tmp_path):
    hf_home = tmp_path / "huggingface"
    hub = hf_home / "hub" / f"models--{config.HF_REPO.replace('/', '--')}"
    calls = {"download": 0, "save": []}

    def fake_download():
        calls["download"] += 1
        hub.mkdir(parents=True, exist_ok=True)
        return str(hub)

    def fake_save(source, bits, path):
        calls["save"].append((source, bits, path))
        (path / "transformer").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HF_HOME", str(hf_home))
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(config, "MODEL_PATH", tmp_path / "z-image-turbo-q8")
    monkeypatch.setattr(config, "KEEP_DOWNLOAD", False)
    monkeypatch.setattr(prepare, "download", fake_download)
    monkeypatch.setattr(prepare, "save_quantized", fake_save)
    return calls, hub


def test_first_use_downloads_quantizes_and_removes_original(env):
    calls, hub = env
    assert core.health()["weights_ready"] is False
    path = prepare.ensure_weights()
    assert calls["download"] == 1 and calls["save"][0][1] == config.QUANTIZE
    assert prepare.weights_ready(path) and not hub.exists()
    assert core.health()["weights_ready"] is True


def test_ready_weights_are_not_downloaded_again(env):
    calls, _ = env
    prepare.ensure_weights()
    prepare.ensure_weights()
    assert calls["download"] == 1


def test_keep_download(env, monkeypatch):
    _, hub = env
    monkeypatch.setattr(config, "KEEP_DOWNLOAD", True)
    prepare.ensure_weights()
    assert hub.exists()


def test_force_rebuilds(env):
    calls, _ = env
    prepare.ensure_weights()
    prepare.ensure_weights(force=True)
    assert calls["download"] == 2
