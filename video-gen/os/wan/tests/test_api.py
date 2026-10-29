"""API + job tests with a fake model; no weights or GPU work needed."""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from wan_service import api, config, core, prepare


class _FakeModel:
    def __init__(self):
        self.calls = []
        self.gate = threading.Event()
        self.gate.set()
        self.fail = None

    def generate_video(self, **kw):
        self.calls.append(kw)
        self.gate.wait(5)
        if self.fail:
            raise self.fail
        for step in (1, 2):
            kw["progress_callback"](SimpleNamespace(phase="denoise", step=step, total_steps=kw["num_inference_steps"]))

        def save(path, overwrite=True):
            Path(path).write_bytes(b"\x00\x00\x00\x18ftypmp42fake")

        return SimpleNamespace(width=kw["width"], height=kw["height"], frame_count=kw["num_frames"], save=save)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    model = _FakeModel()
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    loads = []
    monkeypatch.setattr(core, "_load_model", lambda: loads.append(1) or model)
    model.loads = loads
    monkeypatch.setattr(prepare, "weights_ready", lambda: True)
    core._jobs.clear()
    return model


@pytest.fixture
def client(fake):
    return TestClient(api.app)


def _run(client, payload, wait=10):
    r = client.post("/generate", json=payload)
    assert r.status_code == 202, r.text
    return client.get(f"/jobs/{r.json()['job_id']}", params={"wait_s": wait}).json()


@pytest.mark.parametrize(("duration", "frames"), [(5, 121), (5.04, 121), (2, 49), (1, 25), (0.5, 13)])
def test_frames_snap_to_vae_grid(duration, frames):
    assert core.frames_for(duration) == frames
    assert (frames - 1) % 4 == 0


def test_health(client):
    body = client.get("/health").json()
    assert (body["weights_ready"], body["active_jobs"]) == (True, 0)


def test_job_runs_to_done_with_result(client, fake, tmp_path):
    job = _run(client, {"prompt": "a fox", "width": 850, "height": 490, "seed": 7, "output_name": "fox"})
    assert job["status"] == "done" and job["error"] is None
    res = job["result"]
    assert (res["width"], res["height"], res["frames"], res["duration_s"], res["audio"]) == (832, 480, 121, 5.04, False)
    assert res["name"] == "fox.mp4" and Path(res["path"]).parent == tmp_path
    assert res["url"].endswith("/files/fox.mp4")
    call = fake.calls[0]
    assert (call["seed"], call["num_inference_steps"], call["fps"], call["flow_shift"]) == (7, 25, 24, 3.0)
    # the memory settings that keep 832x480 at ~23 GB on a 48 GB Mac
    assert call["release_denoisers_before_decode"] is True and call["clear_cache_each_step"] is True
    assert client.get("/files/fox.mp4").content.endswith(b"fake")


@pytest.mark.parametrize(("w", "h"), [(1024, 576), (576, 1024), (768, 768)])
def test_sizes_up_to_the_memory_cap_are_accepted(client, fake, w, h):
    job = _run(client, {"prompt": "x", "width": w, "height": h, "steps": 10})
    assert job["status"] == "done" and (job["result"]["width"], job["result"]["height"]) == (w, h)


def test_hd_is_rejected_with_a_clear_message(client):
    r = client.post("/generate", json={"prompt": "x", "width": 1024, "height": 704})
    assert r.status_code == 400 and "1024x576" in r.json()["error"]


def test_each_job_builds_a_fresh_model(client, fake):
    _run(client, {"prompt": "a"})
    _run(client, {"prompt": "b"})
    assert len(fake.loads) == 2


def test_progress_is_visible_while_running(client, fake):
    fake.gate.clear()
    job_id = client.post("/generate", json={"prompt": "x"}).json()["job_id"]
    running = client.get(f"/jobs/{job_id}", params={"wait_s": 0.3}).json()
    assert running["status"] == "running"
    fake.gate.set()
    done = client.get(f"/jobs/{job_id}", params={"wait_s": 10}).json()
    assert done["status"] == "done" and done["phase"] == "done" and done["step"] == done["total_steps"] == 25


def test_concurrent_first_submits_share_one_worker_and_keep_order(fake, monkeypatch):
    """Two requests arriving before the worker exists must not start a second one or reorder clips."""
    import queue as queue_mod

    fake.gate.clear()
    created = []

    class SlowStartThread(threading.Thread):
        def __init__(self, *args, **kwargs):
            # Widen the gap between the `_worker is None` check and the assignment.
            time.sleep(0.05)
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(core.threading, "Thread", SlowStartThread)
    # A worker left by an earlier test is blocked inside the previous queue's get().
    # Swapping the queue keeps it from stealing these jobs; monkeypatch restores both.
    monkeypatch.setattr(core, "_queue", queue_mod.Queue())
    monkeypatch.setattr(core, "_worker", None)

    n = 8
    barrier = threading.Barrier(n)
    submitted: list[dict] = []
    submit_lock = threading.Lock()

    def go(i: int):
        barrier.wait()
        job = core.submit(prompt=f"clip-{i}", width=832, height=480, duration_s=0.5, steps=4)
        with submit_lock:
            submitted.append(job)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(n)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # queue_position is taken under the same lock as the insert, so it is the run order.
        submitted.sort(key=lambda job: job["queue_position"])
        assert [t.name for t in created if t.name == "wan-worker"] == ["wan-worker"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            states = [core.get_job(job["job_id"])["status"] for job in submitted]
            if states.count("running") == 1 and states.count("queued") == n - 1:
                break
            time.sleep(0.01)
        else:
            raise AssertionError(states)

        fake.gate.set()
        for job in submitted:
            done = core.get_job(job["job_id"], wait_s=10)
            assert done["status"] == "done"
        assert [c["prompt"] for c in fake.calls] == [job["prompt"] for job in submitted]
    finally:
        fake.gate.set()
        for job in submitted:
            core.get_job(job["job_id"], wait_s=10)


def test_jobs_queue_in_order(client, fake):
    fake.gate.clear()
    a = client.post("/generate", json={"prompt": "a"}).json()
    b = client.post("/generate", json={"prompt": "b"}).json()
    assert (a["queue_position"], b["queue_position"]) == (0, 1)
    fake.gate.set()
    assert client.get(f"/jobs/{b['job_id']}", params={"wait_s": 10}).json()["status"] == "done"
    assert [c["prompt"] for c in fake.calls] == ["a", "b"]
    assert [j["job_id"] for j in client.get("/jobs").json()] == [b["job_id"], a["job_id"]]


def test_failed_job_reports_error_and_removes_file(client, fake, tmp_path):
    fake.fail = RuntimeError("metal oom")
    job = _run(client, {"prompt": "x", "output_name": "broken"})
    assert job["status"] == "failed" and "metal oom" in job["error"]
    assert not (tmp_path / "broken.mp4").exists()
    fake.fail = None
    assert _run(client, {"prompt": "y"})["status"] == "done"  # the worker survives a failure


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": " "},
        {"prompt": "x", "width": 100},
        {"prompt": "x", "width": 1280},
        {"prompt": "x", "duration_s": 8},
        {"prompt": "x", "steps": 2},
    ],
)
def test_rejects_bad_input_before_queuing(client, payload):
    assert client.post("/generate", json=payload).status_code in (400, 422)
    assert client.get("/jobs").json() == []


def test_missing_image_is_404(client):
    assert client.post("/generate", json={"prompt": "x", "image_path": "/nope.png"}).status_code == 404


def test_img2video_upload_is_cleaned_up_after_job(client, fake):
    files = {"image": ("first.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
    r = client.post("/img2video", data={"prompt": "x", "duration_s": "2"}, files=files)
    assert r.status_code == 202, r.text
    job = client.get(f"/jobs/{r.json()['job_id']}", params={"wait_s": 10}).json()
    assert job["status"] == "done"
    call = fake.calls[0]
    assert call["image_path"].endswith(".png") and call["num_frames"] == 49
    assert not Path(call["image_path"]).exists()


def test_unknown_job_is_404(client):
    assert client.get("/jobs/nope").status_code == 404


def test_get_job_wait_survives_eviction():
    """A finished job may be evicted from _jobs while get_job is blocked on wait()."""
    job_id = "evict-me-test"
    job = {
        "job_id": job_id,
        "status": "running",
        "phase": "denoise",
        "step": 1,
        "total_steps": 4,
        "created_at": 0.0,
        "prompt": "x",
        "result": None,
        "error": None,
    }
    with core._jobs_changed:
        core._jobs[job_id] = job

    result: dict = {}

    def waiter():
        result["job"] = core.get_job(job_id, wait_s=5)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)
    with core._jobs_changed:
        job["status"] = "done"
        job["phase"] = "done"
        job["result"] = {"path": "/tmp/x.mp4"}
        core._jobs.pop(job_id)
        core._jobs_changed.notify_all()
    t.join(timeout=2)
    assert result["job"]["status"] == "done" and result["job"]["result"]["path"] == "/tmp/x.mp4"
    core._jobs.pop(job_id, None)


def test_files_cannot_escape_output_dir(client):
    assert client.get("/files/..%2Fsecret").status_code == 404


def test_mcp_lists_tools():
    import anyio
    from wan_service import mcp_server

    names = {t.name for t in anyio.run(mcp_server.mcp.list_tools)}
    assert names == {"check_health", "generate_video", "get_video_job", "list_video_jobs"}
