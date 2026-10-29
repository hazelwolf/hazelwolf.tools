import json

import httpx
import pytest
from comfyflow_tool import api, core, workflows
from comfyflow_tool.errors import ComfyUnavailable
from fastapi.testclient import TestClient


def make_graph():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox"}, "_meta": {"title": "@prompt"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "a.png"}, "_meta": {"title": "@image"}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}, "_meta": {"title": "Save"}},
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    comfy = tmp_path / "comfy"
    (comfy / "output").mkdir(parents=True)
    (comfy / "output" / "out_00001_.png").write_bytes(b"x")
    monkeypatch.setenv("COMFYFLOW_COMFY_DIR", str(comfy))
    monkeypatch.setenv("COMFYFLOW_WORKFLOWS_DIR", str(comfy / "wf"))
    workflows.save(comfy / "wf", "demo", make_graph(), {"description": "demo flow"})
    seen = {"prompts": [], "uploads": []}
    state = {"done": True}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/prompt":
            body = json.loads(request.content)
            seen["prompts"].append(body["prompt"])
            if body["prompt"]["1"]["inputs"]["text"] == "BAD":
                return httpx.Response(
                    400,
                    json={
                        "error": {"type": "prompt_outputs_failed_validation", "message": "nope"},
                        "node_errors": {
                            "1": {
                                "class_type": "CLIPTextEncode",
                                "errors": [{"message": "Required input is missing", "details": "clip"}],
                            }
                        },
                    },
                )
            return httpx.Response(200, json={"prompt_id": "pid1"})
        if path == "/upload/image":
            seen["uploads"].append(request.content)
            return httpx.Response(200, json={"name": "uploaded.png"})
        if path == "/history/pid1":
            if not state["done"]:
                return httpx.Response(200, json={})
            entry = {
                "status": {"status_str": "success", "messages": []},
                "outputs": {"3": {"images": [{"filename": "out_00001_.png", "subfolder": "", "type": "output"}]}},
            }
            return httpx.Response(200, json={"pid1": entry})
        if path == "/history":
            return httpx.Response(
                200,
                json={
                    "pid1": {"prompt": [5, "pid1", seen["prompts"][-1] if seen["prompts"] else make_graph(), {}, ["3"]]}
                },
            )
        if path == "/queue":
            return httpx.Response(200, json={"queue_running": [[0, "pid2"]], "queue_pending": []})
        if path == "/system_stats":
            return httpx.Response(
                200, json={"system": {"comfyui_version": "9"}, "devices": [{"name": "gpu", "vram_free": 2**30}]}
            )
        return httpx.Response(404)

    monkeypatch.setattr(core, "_transport", httpx.MockTransport(handler))
    return seen, state


def test_run_uploads_file_applies_params_and_returns_outputs(env, tmp_path):
    seen, _ = env
    img = tmp_path / "in.png"
    img.write_bytes(b"png")
    result = core.run_workflow("demo", {"prompt": "a cat", "image": str(img)})
    sent = seen["prompts"][0]
    assert sent["1"]["inputs"]["text"] == "a cat"
    assert sent["2"]["inputs"]["image"] == "uploaded.png"
    assert len(seen["uploads"]) == 1
    assert result["status"] == "success"
    assert result["files"][0]["kind"] == "image" and result["files"][0]["exists"]


def test_missing_file_param_is_treated_as_comfy_input_name(env):
    seen, _ = env
    core.run_workflow("demo", {"image": "already_there.png"})
    assert seen["prompts"][0]["2"]["inputs"]["image"] == "already_there.png"
    assert not seen["uploads"]


def test_rejection_message_is_readable(env):
    with pytest.raises(core.FlowError, match="Required input is missing"):
        core.run_workflow("demo", {"prompt": "BAD"})


def test_no_wait_and_timeout(env):
    _, state = env
    state["done"] = False
    assert core.run_workflow("demo", wait=False)["status"] == "queued"
    assert core.run_workflow("demo", timeout_s=0.01)["status"] == "timeout"


def test_import_and_cancel(env):
    result = core.import_workflow("copy", description="imported")
    assert result["description"] == "imported"
    assert {p["name"] for p in result["params"]} >= {"prompt", "image"}
    assert core.cancel_job("pid2")["was_running"] is True


def test_api_routes(env):
    http = TestClient(api.app)
    assert http.get("/health").json()["comfyui_version"] == "9"
    assert http.get("/v1/workflows").json()["workflows"][0]["params"] == ["image", "prompt"]
    assert http.get("/v1/workflows/missing").status_code == 404
    body = http.post("/v1/workflows/demo/run", json={"params": {"prompt": "hi"}}).json()
    assert body["status"] == "success"
    assert http.post("/v1/workflows/demo/run", json={"params": {"bogus": 1}}).status_code == 400


def test_comfy_down(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(core, "_transport", httpx.MockTransport(boom))
    with pytest.raises(ComfyUnavailable, match="run.sh"):
        core.health()
