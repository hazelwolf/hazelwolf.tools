"""Wrapper tests against a mocked upstream backend (no models, no running server)."""

import threading

import httpx
import pytest
from fastapi.testclient import TestClient
from voicestudio_service import api, config, core

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "


def _backend(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/health":
        return httpx.Response(200, json={"status": "ok", "device": "mps"})
    if path == "/profiles" and request.method == "GET":
        return httpx.Response(200, json=[{"id": "p1", "name": "Ava", "kind": "clone", "ref_path": "/x"}])
    if path == "/profiles" and request.method == "POST":
        assert b'name="kind"\r\n\r\nclone' in request.content
        return httpx.Response(200, json={"id": "p2", "name": "Me", "kind": "clone"})
    if path == "/personalities":
        return httpx.Response(200, json=[{"name": "Narrator"}])
    if path == "/generate":
        assert b"hello there" in request.content
        headers = {"X-Audio-Id": "a1", "X-Audio-Duration": "1.5", "X-Gen-Time": "0.4"}
        return httpx.Response(200, content=WAV, headers=headers)
    if path == "/transcribe":
        return httpx.Response(200, json={"text": "hello", "language": "en"})
    if path == "/profiles/missing":
        return httpx.Response(404, json={"detail": "Profile not found"})
    return httpx.Response(404, json={"detail": "nope"})


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "API_KEY", None)
    real = httpx.Client
    monkeypatch.setattr(
        core, "_client", lambda timeout=30: real(base_url="http://backend", transport=httpx.MockTransport(_backend))
    )
    return TestClient(api.app)


def test_health(http):
    body = http.get("/health").json()
    assert body["backend_ready"] is True
    assert body["backend"]["device"] == "mps"


def test_voices_are_trimmed(http):
    assert http.get("/voices").json() == [{"id": "p1", "name": "Ava", "kind": "clone"}]
    assert http.get("/personalities").json() == [{"name": "Narrator"}]


def test_generate_writes_wav_and_serves_it(http, tmp_path):
    r = http.post("/generate", json={"text": "hello there", "output_name": "greet"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "greet.wav"
    assert body["duration_s"] == 1.5
    assert (tmp_path / "greet.wav").read_bytes() == WAV
    assert http.get("/files/greet.wav").content == WAV
    # same name again does not overwrite
    assert http.post("/generate", json={"text": "hello there", "output_name": "greet"}).json()["name"] == "greet-2.wav"


def test_existing_output_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    (tmp_path / "greet.wav").write_bytes(b"original")
    path = core._write_output("greet", b"new")
    assert path.name == "greet-2.wav"
    assert (tmp_path / "greet.wav").read_bytes() == b"original"
    assert path.read_bytes() == b"new"


def test_parallel_outputs_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    barrier = threading.Barrier(8)
    found: list[tuple[str, bytes]] = []
    lock = threading.Lock()

    def write(i: int):
        payload = f"audio-{i}".encode()
        barrier.wait(2)
        path = core._write_output("greet", payload)
        with lock:
            found.append((path.name, payload))

    threads = [threading.Thread(target=write, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    names = [name for name, _ in found]
    assert len(names) == len(set(names)) == 8
    assert "greet.wav" in names
    assert "greet-2.wav" in names
    assert "greet-1.wav" not in names
    for name, payload in found:
        assert (tmp_path / name).read_bytes() == payload


def test_generate_validation(http):
    assert http.post("/generate", json={"text": "hi", "speed": 3}).status_code == 422
    assert http.post("/generate", json={"text": "   "}).status_code == 400


def test_clone_and_transcribe(http):
    files = {"ref_audio": ("me.wav", WAV, "audio/wav")}
    assert http.post("/voices/clone", data={"name": "Me"}, files=files).json()["profile_id"] == "p2"
    r = http.post("/transcribe", files={"audio": ("a.wav", WAV, "audio/wav")})
    assert r.json()["text"] == "hello"


def test_upload_routes_do_not_stall_health(http, monkeypatch):
    """A slow clone or transcribe must not block the event loop (and /health)."""
    started = threading.Event()
    release = threading.Event()

    def slow(*_args, **_kwargs):
        started.set()
        assert release.wait(2)
        return {"profile_id": "p2", "name": "Me", "kind": "clone"}

    monkeypatch.setattr(core, "clone_voice_bytes", slow)
    result = {}

    def do_clone():
        files = {"ref_audio": ("me.wav", WAV, "audio/wav")}
        result["resp"] = http.post("/voices/clone", data={"name": "Me"}, files=files)

    worker = threading.Thread(target=do_clone)
    worker.start()
    assert started.wait(2)
    health: dict = {}

    def do_health():
        health["resp"] = http.get("/health")

    health_thread = threading.Thread(target=do_health)
    health_thread.start()
    health_thread.join(1)
    stalled = health_thread.is_alive()
    release.set()
    health_thread.join(2)
    worker.join(2)
    assert not stalled
    assert health["resp"].status_code == 200
    assert health["resp"].json()["status"] == "ok"
    assert result["resp"].status_code == 200


def test_backend_errors_pass_through(http):
    r = http.delete("/voices/missing")
    assert r.status_code == 404
    assert r.json() == {"error": "Profile not found"}


def test_file_path_traversal_blocked(http):
    assert http.get("/files/..%2Fsecret.wav").status_code == 404


def test_backend_down(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BACKEND_URL", "http://127.0.0.1:9")
    with pytest.raises(core.ServiceError) as e:
        core.list_voices()
    assert e.value.status == 503
    assert core.health()["backend_ready"] is False


def test_local_file_inputs(http, tmp_path):
    ref = tmp_path / "ref.wav"
    ref.write_bytes(WAV)
    assert core.clone_voice("Me", str(ref))["profile_id"] == "p2"
    assert core.transcribe(str(ref))["text"] == "hello"
    with pytest.raises(core.ServiceError):
        core.transcribe(str(tmp_path / "missing.wav"))
    bad = tmp_path / "notes.txt"
    bad.write_text("x")
    with pytest.raises(core.ServiceError):
        core.transcribe(str(bad))
