"""Talk to ComfyUI and run workflows. Shared by the CLI, the HTTP API and the MCP server."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

from . import workflows
from .errors import ComfyUnavailable, FlowError, NotFound, WorkflowError

_here = Path(__file__).resolve()
_root = next(p for p in _here.parents if (p / "INSTRUCTIONS.md").exists())
load_dotenv(_root / ".env")
load_dotenv(_here.parents[2] / ".env", override=True)

DEFAULT_COMFY_DIR = "creative/os/creative-workflows"
_transport: httpx.BaseTransport | None = None  # tests inject a fake ComfyUI here


def tool_root() -> Path:
    return _here.parents[2]


def _path_from_env(var: str, default: str) -> Path:
    path = Path(os.environ.get(var) or default).expanduser()
    return path if path.is_absolute() else _root / path


def comfy_url() -> str:
    return (os.environ.get("COMFYFLOW_COMFY_URL") or "http://127.0.0.1:8188").rstrip("/")


def comfy_dir() -> Path:
    return _path_from_env("COMFYFLOW_COMFY_DIR", DEFAULT_COMFY_DIR)


def workflows_dir() -> Path:
    default = str(comfy_dir() / "workflows" / "api")
    return _path_from_env("COMFYFLOW_WORKFLOWS_DIR", default)


def bind_host() -> str:
    return os.environ.get("COMFYFLOW_HOST") or "127.0.0.1"


def bind_port() -> int:
    return int(os.environ.get("COMFYFLOW_PORT") or 8130)


def default_timeout() -> float:
    return float(os.environ.get("COMFYFLOW_TIMEOUT_S") or 3600)


def _client() -> httpx.Client:
    return httpx.Client(base_url=comfy_url(), timeout=60, transport=_transport)


def _call(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        with _client() as http:
            return http.request(method, path, **kwargs)
    except httpx.TransportError:
        raise ComfyUnavailable(
            f"ComfyUI is not reachable at {comfy_url()}. Start it with creative/os/creative-workflows/run.sh"
        ) from None


def health() -> dict:
    stats = _call("GET", "/system_stats").json()
    device = (stats.get("devices") or [{}])[0]
    return {
        "status": "ok",
        "comfy_url": comfy_url(),
        "comfyui_version": stats.get("system", {}).get("comfyui_version"),
        "device": device.get("name"),
        "vram_free_mb": round(device.get("vram_free", 0) / 2**20),
        "workflows_dir": str(workflows_dir()),
        "workflows": len(list_workflows()),
    }


def list_workflows() -> list[dict]:
    directory = workflows_dir()
    return [workflows.summary(directory, p) for p in sorted(directory.glob("*.json"))] if directory.is_dir() else []


def describe_workflow(name: str) -> dict:
    graph, meta = workflows.load(workflows_dir(), name)
    exposed = workflows.discover(graph, meta)
    return {
        "name": name,
        "description": meta.get("description", ""),
        "params": [p.to_dict() for p in exposed.values()],
        "output_nodes": [
            f"{nid} ({n['class_type']})" for nid, n in graph.items() if n["class_type"].startswith(("Save", "Preview"))
        ],
        "notes": "Seed parameters are randomized unless you pass one. File parameters take a local path.",
    }


def _upload(path_text: str) -> str:
    path = Path(path_text).expanduser()
    if not path.is_file():
        return path_text  # already a filename in ComfyUI's input folder
    with path.open("rb") as handle:
        resp = _call("POST", "/upload/image", files={"image": (path.name, handle)}, data={"overwrite": "true"})
    if resp.status_code != 200:
        raise FlowError(f"upload of {path.name} failed: {resp.text[:200]}", 502)
    return resp.json()["name"]


def _reject_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:500]
    err = body.get("error") or {}
    parts = [f"{err.get('type', 'error')}: {err.get('message', '')}".strip()]
    for node_id, info in (body.get("node_errors") or {}).items():
        for item in info.get("errors", []):
            parts.append(f"node {node_id} ({info.get('class_type')}): {item.get('message')} {item.get('details', '')}")
    return "; ".join(p for p in parts if p)


def submit(name: str, params: dict | None = None, randomize_seed: bool = True) -> dict:
    graph, meta = workflows.load(workflows_dir(), name)
    exposed = workflows.discover(graph, meta)
    values = dict(params or {})
    for key, value in values.items():
        param = exposed.get(key)
        if param and param.type == "file":
            values[key] = _upload(str(value))
        elif not param and "." in key:
            node_id, _, input_name = key.partition(".")
            if workflows.is_file_target(graph, node_id, input_name):
                values[key] = _upload(str(value))
    final, seeds = workflows.apply_params(graph, exposed, values, randomize_seed)
    resp = _call("POST", "/prompt", json={"prompt": final, "client_id": uuid.uuid4().hex})
    if resp.status_code != 200:
        raise FlowError(f"ComfyUI rejected the workflow: {_reject_message(resp)}", 400)
    return {"prompt_id": resp.json()["prompt_id"], "seeds": seeds}


def _media_kind(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        return "image"
    if suffix in (".mp4", ".webm", ".mov", ".mkv"):
        return "video"
    if suffix in (".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a"):
        return "audio"
    return "file"


def _summarize(prompt_id: str, entry: dict, seeds: dict | None = None, elapsed: float | None = None) -> dict:
    status = entry.get("status", {})
    error = None
    for event, data in status.get("messages", []):
        if event == "execution_error":
            message = str(data.get("exception_message", "")).strip()
            error = f"{data.get('node_type')} (node {data.get('node_id')}): {message}"
        elif event == "execution_interrupted" and not error:
            error = "interrupted"
    files, texts = [], []
    for node_id, output in entry.get("outputs", {}).items():
        for items in output.values():
            for item in items if isinstance(items, list) else []:
                if isinstance(item, str):
                    texts.append({"node": node_id, "text": item})
                elif isinstance(item, dict) and "filename" in item:
                    path = comfy_dir() / item.get("type", "output") / item.get("subfolder", "") / item["filename"]
                    files.append(
                        {
                            "node": node_id,
                            "kind": _media_kind(path.suffix),
                            "path": str(path),
                            "filename": item["filename"],
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                            "exists": path.exists(),
                        }
                    )
    out = {
        "prompt_id": prompt_id,
        "status": "success" if status.get("status_str") == "success" else "error",
        "files": [f for f in files if f["type"] == "output"] or files,
        "texts": texts,
    }
    if error:
        out["error"] = error
    if seeds:
        out["seeds"] = seeds
    if elapsed is not None:
        out["seconds"] = round(elapsed, 1)
    return out


def get_job(prompt_id: str) -> dict:
    entry = _call("GET", f"/history/{prompt_id}").json().get(prompt_id)
    if entry:
        return _summarize(prompt_id, entry)
    queue = _call("GET", "/queue").json()
    if any(item[1] == prompt_id for item in queue.get("queue_running", [])):
        return {"prompt_id": prompt_id, "status": "running"}
    if any(item[1] == prompt_id for item in queue.get("queue_pending", [])):
        return {"prompt_id": prompt_id, "status": "queued"}
    raise NotFound(f"no job {prompt_id} in ComfyUI's queue or history")


def run_workflow(
    name: str,
    params: dict | None = None,
    wait: bool = True,
    timeout_s: float | None = None,
    randomize_seed: bool = True,
) -> dict:
    started = time.monotonic()
    job = submit(name, params, randomize_seed)
    if not wait:
        return {**job, "status": "queued"}
    limit = timeout_s if timeout_s is not None else default_timeout()
    while time.monotonic() - started < limit:
        entry = _call("GET", f"/history/{job['prompt_id']}").json().get(job["prompt_id"])
        if entry:
            return _summarize(job["prompt_id"], entry, job["seeds"], time.monotonic() - started)
        time.sleep(1)
    return {**job, "status": "timeout", "hint": "still running in ComfyUI; poll with get_job"}


def cancel_job(prompt_id: str) -> dict:
    running = any(i[1] == prompt_id for i in _call("GET", "/queue").json().get("queue_running", []))
    if running:
        _call("POST", "/interrupt")
    else:
        _call("POST", "/queue", json={"delete": [prompt_id]})
    return {"prompt_id": prompt_id, "cancelled": True, "was_running": running}


def import_workflow(name: str, prompt_id: str | None = None, description: str = "", overwrite: bool = False) -> dict:
    """Save a workflow ComfyUI already ran (default: the latest) as `<name>.json`, with `@` titles scaffolded."""
    workflows.check_name(name)
    history = _call("GET", "/history", params={"max_items": 50}).json()
    if prompt_id:
        entry = history.get(prompt_id) or _call("GET", f"/history/{prompt_id}").json().get(prompt_id)
    else:
        entry = max(history.values(), key=lambda e: e["prompt"][0], default=None)
        prompt_id = entry["prompt"][1] if entry else None
    if not entry:
        raise NotFound("no matching run in ComfyUI's history; run the workflow once in the ComfyUI UI first")
    graph = workflows.scaffold_titles(entry["prompt"][2])
    path = workflows.save(
        workflows_dir(), name, graph, {"description": description, "imported_from": prompt_id}, overwrite
    )
    return {"saved": str(path), "imported_from": prompt_id, **describe_workflow(name)}


__all__ = ["FlowError", "WorkflowError"]
