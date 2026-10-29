"""API + core tests with a fake pipeline; no weights or GPU work needed."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ltx_service import api, config, core, prepare


class _FakePipe:
    def __init__(self):
        self.calls = []

    def generate_and_save(self, **kwargs):
        self.calls.append(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        return kwargs["output_path"]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    pipe = _FakePipe()
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "IDLE_UNLOAD_S", 0)
    monkeypatch.setattr(core, "_load_pipeline", lambda: (pipe, "fake"))
    monkeypatch.setattr(core, "_pipe", None)
    monkeypatch.setattr(prepare, "weights_ready", lambda: True)
    return pipe


@pytest.fixture
def client(fake):
    return TestClient(api.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["loaded"] is False and body["weights_ready"] is True


def test_hf_revision_pinned_only_for_default_repo():
    assert config.resolve_hf_revision(config.DEFAULT_HF_REPO, {}) == config.PINNED_HF_REVISION
    assert config.resolve_hf_revision("dgrauet/ltx-2.5-mlx-q4", {}) is None
    assert config.resolve_hf_revision("dgrauet/ltx-2.5-mlx-q4", {"LTX_HF_REVISION": "deadbeef"}) == "deadbeef"


@pytest.mark.parametrize(("duration", "fps", "frames"), [(5, 24, 121), (1, 24, 25), (10, 30, 305), (20, 24, 481)])
def test_frames_snap_to_vae_grid(duration, fps, frames):
    assert core.frames_for(duration, fps) == frames
    assert (frames - 1) % 8 == 0


def test_generate_writes_mp4_and_snaps_size(client, fake, tmp_path):
    r = client.post("/generate", json={"prompt": "a fox", "width": 800, "height": 500, "seed": 7, "output_name": "fox"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["width"], body["height"], body["frames"], body["duration_s"]) == (768, 448, 121, 5.04)
    assert body["name"] == "fox.mp4" and Path(body["path"]).parent == tmp_path
    call = fake.calls[0]
    assert (call["seed"], call["num_frames"], call["frame_rate"], call["image"]) == (7, 121, 24.0, None)
    assert client.get(f"/files/{body['name']}").content.endswith(b"fake")


def test_auto_duration(client, fake, monkeypatch):
    monkeypatch.setattr(core, "_probe_frames", lambda _: 97)
    body = client.post("/generate", json={"prompt": "x", "duration_s": None}).json()
    from ltx_pipelines_mlx.utils.types import AutoDuration

    assert isinstance(fake.calls[0]["num_frames"], AutoDuration)
    assert (body["frames"], body["duration_s"]) == (97, 4.04)


def test_same_output_name_does_not_overwrite(client):
    a = client.post("/generate", json={"prompt": "x", "output_name": "same"}).json()["name"]
    b = client.post("/generate", json={"prompt": "x", "output_name": "same"}).json()["name"]
    assert (a, b) == ("same.mp4", "same-2.mp4")


def test_failed_generation_removes_reserved_file(client, fake, tmp_path):
    def boom(**_):
        raise RuntimeError("gpu")

    fake.generate_and_save = boom
    with pytest.raises(RuntimeError):
        client.post("/generate", json={"prompt": "x", "output_name": "broken"})
    assert not (tmp_path / "broken.mp4").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": " "},
        {"prompt": "x", "width": 100},
        {"prompt": "x", "duration_s": 30},
        {"prompt": "x", "fps": 60},
    ],
)
def test_rejects_bad_input(client, payload):
    assert client.post("/generate", json=payload).status_code in (400, 422)


def test_img2video_upload_is_cleaned_up(client, fake):
    files = {"image": ("first.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
    r = client.post("/img2video", data={"prompt": "x", "duration_s": "2"}, files=files)
    assert r.status_code == 200, r.text
    call = fake.calls[0]
    assert call["image"].endswith(".png") and call["num_frames"] == 49
    assert not Path(call["image"]).exists()


def test_missing_image_is_404(client):
    assert client.post("/generate", json={"prompt": "x", "image_path": "/nope.png"}).status_code == 404


def test_gated_weights_surface_as_503(client, monkeypatch):
    def gated():
        raise core.ServiceError("gated", status=503)

    monkeypatch.setattr(core, "_load_pipeline", gated)
    r = client.post("/generate", json={"prompt": "x"})
    assert r.status_code == 503 and r.json()["error"] == "gated"


def test_files_cannot_escape_output_dir(client):
    assert client.get("/files/..%2Fsecret").status_code == 404


def test_unload(client):
    client.post("/generate", json={"prompt": "x"})
    assert client.post("/unload").json() == {"unloaded": True}
    assert client.get("/health").json()["loaded"] is False


def test_mcp_lists_tools():
    import anyio
    from ltx_service import mcp_server

    names = {t.name for t in anyio.run(mcp_server.mcp.list_tools)}
    assert names == {"check_health", "generate_video", "unload_model"}


def test_ensure_weights_explains_gating(monkeypatch, tmp_path):
    import httpx
    from huggingface_hub.errors import GatedRepoError

    def gated(*_, **kw):
        if kw.get("local_files_only"):
            raise FileNotFoundError
        raise GatedRepoError("401", response=httpx.Response(401, request=httpx.Request("GET", "https://hf.co")))

    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(config, "MODEL_PATH", None)
    monkeypatch.setattr("huggingface_hub.snapshot_download", gated)
    with pytest.raises(prepare.WeightsUnavailable, match="Accept the LTX-2.x Community License"):
        prepare.ensure_weights()
