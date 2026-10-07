from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from localbox_tool import api, core


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "in"
    monkeypatch.setenv("LOCALBOX_DESTINATIONS", f"comfy={folder}")
    monkeypatch.setenv("LOCALBOX_MAX_MB", "1")
    monkeypatch.setenv("LOCALBOX_HOST", "0.0.0.0")
    monkeypatch.setenv("LOCALBOX_PORT", "8120")
    return TestClient(api.app), folder


def test_health_and_destinations(client):
    http, folder = client
    health = http.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["host"] == "0.0.0.0"
    assert body["port"] == 8120
    assert body["destinations"][0]["tag"] == "comfy"
    assert body["destinations"][0]["path"] == str(folder)
    listed = http.get("/destinations").json()
    assert listed["default"] == "comfy"


def test_page_and_upload(client):
    http, folder = client
    page = http.get("/")
    assert page.status_code == 200
    assert "Drop files here" in page.text
    uploaded = http.post(
        "/upload",
        data={"destination": "comfy"},
        files={"file": ("frame.jpg", b"jpeg-bytes", "image/jpeg")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["name"] == "frame.jpg"
    assert Path(body["path"]) == folder / "frame.jpg"
    assert (folder / "frame.jpg").read_bytes() == b"jpeg-bytes"


def test_upload_error_shape(client):
    http, _folder = client
    bad = http.post(
        "/upload",
        data={"destination": "comfy"},
        files={"file": ("notes.txt", b"nope", "text/plain")},
    )
    assert bad.status_code == 400
    assert "error" in bad.json()


def test_core_health_matches_route(client):
    http, _folder = client
    assert http.get("/health").json()["max_mb"] == core.max_bytes() // (1024 * 1024)
