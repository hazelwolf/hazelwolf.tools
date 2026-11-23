"""API + core tests with a fake model; no weights or GPU needed."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from imagegen_service import api, config, core


class _FakeImage:
    def save(self, path, overwrite=False, export_json_metadata=False):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")


class _FakeModel:
    def __init__(self):
        self.calls = []
        self.loads = []

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeImage()


@pytest.fixture
def fake(monkeypatch, tmp_path):
    model = _FakeModel()

    def load(key):
        model.loads.append(key)
        return model, f"fake-{key}"

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "IDLE_UNLOAD_S", 0)
    monkeypatch.setattr(core, "_load_model", load)
    monkeypatch.setattr(core, "_model", None)
    monkeypatch.setattr(core, "_model_key", None)
    return model


@pytest.fixture
def client(fake):
    return TestClient(api.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["loaded"] is False


def test_generate_writes_png_and_rounds_size(client, fake, tmp_path):
    r = client.post("/generate", json={"prompt": "a fox", "width": 1000, "height": 777, "seed": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["width"], body["height"]) == (992, 768)
    img = body["images"][0]
    assert img["seed"] == 7 and Path(img["path"]).parent == tmp_path
    assert fake.calls[0]["num_inference_steps"] == 9
    assert client.get(f"/files/{img['name']}").content.startswith(b"\x89PNG")
    assert client.get("/health").json()["loaded"] is True


def test_count_uses_consecutive_seeds_and_unique_names(client, fake):
    body = client.post("/generate", json={"prompt": "x", "seed": 10, "count": 3, "output_name": "fox"}).json()
    assert [i["seed"] for i in body["images"]] == [10, 11, 12]
    assert [i["name"] for i in body["images"]] == ["fox-s10.png", "fox-s11.png", "fox-s12.png"]


def test_same_output_name_does_not_overwrite(client):
    a = client.post("/generate", json={"prompt": "x", "output_name": "same"}).json()["images"][0]["name"]
    b = client.post("/generate", json={"prompt": "x", "output_name": "same"}).json()["images"][0]["name"]
    assert (a, b) == ("same.png", "same-2.png")


@pytest.mark.parametrize(
    "payload",
    [{"prompt": " "}, {"prompt": "x", "width": 100}, {"prompt": "x", "count": 9}, {"prompt": "x", "steps": 0}],
)
def test_rejects_bad_input(client, payload):
    assert client.post("/generate", json=payload).status_code in (400, 422)


def test_img2img_upload_is_cleaned_up(client, fake, tmp_path):
    files = {"image": ("init.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
    r = client.post("/img2img", data={"prompt": "x", "image_strength": "0.5"}, files=files)
    assert r.status_code == 200, r.text
    call = fake.calls[0]
    assert call["image_strength"] == 0.5 and call["image_path"].endswith(".png")
    assert not Path(call["image_path"]).exists()


def test_img2img_rejects_unknown_type(client):
    files = {"image": ("init.gif", io.BytesIO(b"GIF89a"), "image/gif")}
    assert client.post("/img2img", data={"prompt": "x"}, files=files).status_code == 400


def test_missing_init_image_is_404(client):
    assert client.post("/generate", json={"prompt": "x", "image_path": "/nope.png"}).status_code == 404


def test_files_cannot_escape_output_dir(client):
    assert client.get("/files/..%2Fsecret").status_code == 404


def test_unload(client):
    client.post("/generate", json={"prompt": "x"})
    assert client.post("/unload").json() == {"unloaded": True}
    assert client.get("/health").json()["loaded"] is False


def test_boogu_uses_its_own_steps_and_no_img2img_args(client, fake):
    body = client.post("/generate", json={"prompt": 'a poster reading "SALE"', "model": "boogu"}).json()
    assert body["model"] == "boogu" and body["steps"] == 8
    call = fake.calls[0]
    assert call["num_inference_steps"] == 8 and "image_path" not in call and "image_strength" not in call
    assert client.get("/health").json()["loaded_model"] == "boogu"


def test_switching_models_reloads_one_at_a_time(client, fake):
    for m in ("zimage", "zimage", "boogu", "zimage"):
        assert client.post("/generate", json={"prompt": "x", "model": m}).status_code == 200
    assert fake.loads == ["zimage", "boogu", "zimage"]


def test_explicit_steps_override_the_model_default(client, fake):
    client.post("/generate", json={"prompt": "x", "model": "boogu", "steps": 4})
    assert fake.calls[0]["num_inference_steps"] == 4


def test_boogu_rejects_img2img(client, tmp_path):
    init = tmp_path / "init.png"
    init.write_bytes(b"\x89PNG fake")
    r = client.post("/generate", json={"prompt": "x", "model": "boogu", "image_path": str(init)})
    assert r.status_code == 400 and "img2img" in r.json()["error"]


def test_unknown_model_is_rejected(client, fake):
    assert client.post("/generate", json={"prompt": "x", "model": "flux"}).status_code == 422
    with pytest.raises(core.ServiceError):
        core.generate("x", model="flux")


def test_health_lists_both_models(client):
    models = client.get("/health").json()["models"]
    assert set(models) == {"zimage", "boogu"}
    assert models["boogu"]["default_steps"] == 8 and models["boogu"]["img2img"] is False


def test_mcp_lists_tools():
    import anyio
    from imagegen_service import mcp_server

    names = {t.name for t in anyio.run(mcp_server.mcp.list_tools)}
    assert names == {"check_health", "generate_image", "unload_model"}
