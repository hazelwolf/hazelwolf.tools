"""Workflow files: load, find exposed parameters, apply values, scaffold titles. No network.

A workflow is a ComfyUI API-format JSON file (node id -> {class_type, inputs, _meta}). A node whose
title starts with `@` exposes its literal inputs as parameters. Optional metadata lives under the
top-level key `_comfyflow` and is removed before the graph is sent to ComfyUI.
"""

from __future__ import annotations

import copy
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import NotFound, WorkflowError

META_KEY = "_comfyflow"
SEED_INPUTS = frozenset({"seed", "noise_seed"})
FILE_INPUTS = {"LoadImage": "image", "LoadAudio": "audio", "LoadVideo": "video"}
_PRIMITIVES = frozenset(
    {"PrimitiveInt", "PrimitiveFloat", "PrimitiveString", "PrimitiveStringMultiline", "PrimitiveBoolean"}
)
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass
class Param:
    name: str
    type: str  # string | integer | number | boolean | file
    default: object
    targets: list[tuple[str, str]] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type, "default": self.default, "description": self.description}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def is_link(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _type_of(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def coerce(name: str, ptype: str, value: object) -> object:
    try:
        if ptype in ("string", "file"):
            return str(value)
        if ptype == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in ("true", "1", "yes", "on"):
                return True
            if text in ("false", "0", "no", "off"):
                return False
            raise ValueError(text)
        if isinstance(value, bool):
            raise ValueError("boolean")
        if ptype == "integer":
            number = float(value)
            if number != int(number):
                raise ValueError(value)
            return int(number)
        return float(value)
    except (TypeError, ValueError):
        raise WorkflowError(f"parameter '{name}' expects {ptype}, got {value!r}") from None


def is_api_format(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    nodes = {k: v for k, v in data.items() if k != META_KEY}
    return bool(nodes) and all(isinstance(v, dict) and "class_type" in v for v in nodes.values())


def split(data: dict) -> tuple[dict, dict]:
    graph = {k: v for k, v in data.items() if k != META_KEY}
    return graph, data.get(META_KEY) or {}


def discover(graph: dict, meta: dict | None = None) -> dict[str, Param]:
    """Parameters exposed by nodes titled `@name`. One literal input -> `name`; several -> `name.input`."""
    docs = (meta or {}).get("params", {})
    found: dict[str, Param] = {}
    for node_id, node in graph.items():
        title = (node.get("_meta") or {}).get("title", "")
        base = slug(title[1:]) if title.startswith("@") else ""
        if not base:
            continue
        literals = {k: v for k, v in node.get("inputs", {}).items() if not is_link(v)}
        for key, value in literals.items():
            name = f"{base}.{key}" if len(literals) > 1 else base
            if name in found:
                raise WorkflowError(f"two nodes expose the parameter '{name}'; node titles must be unique")
            ptype = "file" if FILE_INPUTS.get(node.get("class_type")) == key else _type_of(value)
            found[name] = Param(name, ptype, value, [(node_id, key)], docs.get(name, ""))
    return found


def is_file_target(graph: dict, node_id: str, key: str) -> bool:
    return FILE_INPUTS.get(graph.get(node_id, {}).get("class_type")) == key


def apply_params(
    graph: dict, exposed: dict[str, Param], supplied: dict, randomize_seed: bool = True
) -> tuple[dict, dict]:
    """Return a copy of the graph with values applied, and the seeds that were used.

    Keys are exposed names or raw `node_id.input`. Exposed seed inputs that were not supplied get a
    fresh random value when `randomize_seed` is true.
    """
    out = copy.deepcopy(graph)
    for key, value in supplied.items():
        if key in exposed:
            param = exposed[key]
            value = coerce(key, param.type, value)
            for node_id, input_name in param.targets:
                out[node_id]["inputs"][input_name] = value
            continue
        node_id, _, input_name = key.partition(".")
        node = out.get(node_id)
        if not node or input_name not in node.get("inputs", {}):
            valid = ", ".join(sorted(exposed)) or "none (title nodes `@name` in ComfyUI)"
            raise WorkflowError(f"unknown parameter '{key}'. Exposed parameters: {valid}. Raw form: node_id.input")
        current = node["inputs"][input_name]
        if is_link(current):
            raise WorkflowError(f"'{key}' is wired to another node; set the source node's value instead")
        node["inputs"][input_name] = coerce(key, _type_of(current), value)

    seeds: dict[str, int] = {}
    for name, param in exposed.items():
        if not any(k in SEED_INPUTS for _, k in param.targets):
            continue
        if name in supplied:
            seeds[name] = int(supplied[name])
        elif randomize_seed:
            seeds[name] = random.randrange(2**48)
            for node_id, input_name in param.targets:
                if input_name in SEED_INPUTS:
                    out[node_id]["inputs"][input_name] = seeds[name]
    return out, seeds


def scaffold_titles(graph: dict) -> dict:
    """Give common nodes an `@name` title so a freshly imported workflow is usable. Existing `@` titles win."""
    out = copy.deepcopy(graph)
    taken = {slug(t[1:]) for t in ((n.get("_meta") or {}).get("title", "") for n in out.values()) if t.startswith("@")}
    consumers: dict[str, set[str]] = {}
    for node in out.values():
        for key, value in node.get("inputs", {}).items():
            if is_link(value):
                consumers.setdefault(value[0], set()).add(key)

    for node_id, node in out.items():
        meta = node.setdefault("_meta", {})
        if meta.get("title", "").startswith("@"):
            continue
        cls = node.get("class_type", "")
        inputs = node.get("inputs", {})
        base = None
        if cls in _PRIMITIVES:
            base = slug(meta.get("title") or cls)
        elif cls in FILE_INPUTS:
            base = FILE_INPUTS[cls]
        elif cls in ("KSampler", "KSamplerAdvanced"):
            base = "sampler"
        elif (
            cls.startswith("Empty")
            and "Latent" in cls
            and not is_link(inputs.get("width", []))
            and not is_link(inputs.get("height", []))
            and {"width", "height"} <= inputs.keys()
        ):
            base = "size"
        elif cls == "CLIPTextEncode" and "text" in inputs and not is_link(inputs["text"]):
            used_as = consumers.get(node_id, set())
            base = "negative_prompt" if "negative" in used_as else "prompt" if "positive" in used_as else None
        if not base:
            continue
        name, n = base, 2
        while name in taken:
            name, n = f"{base}_{n}", n + 1
        taken.add(name)
        meta["title"] = f"@{name}"
    return out


def check_name(name: str) -> str:
    if not _NAME_RE.fullmatch(name or ""):
        raise WorkflowError("workflow name may use letters, digits, '_', '-' and '.' only")
    return name


def workflow_path(directory: Path, name: str) -> Path:
    return directory / f"{check_name(name)}.json"


def load(directory: Path, name: str) -> tuple[dict, dict]:
    path = workflow_path(directory, name)
    if not path.is_file():
        raise NotFound(f"workflow '{name}' not found in {directory}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{path.name} is not valid JSON: {exc}") from None
    if not is_api_format(data):
        raise WorkflowError(
            f"{path.name} is not API format. In ComfyUI use Workflow > Export (API), or run it once and "
            "use import_workflow."
        )
    return split(data)


def save(directory: Path, name: str, graph: dict, meta: dict, overwrite: bool = False) -> Path:
    path = workflow_path(directory, name)
    if path.exists() and not overwrite:
        raise WorkflowError(f"workflow '{name}' already exists; pass overwrite to replace it")
    directory.mkdir(parents=True, exist_ok=True)
    payload = {META_KEY: meta, **graph} if meta else dict(graph)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    return path


def summary(directory: Path, path: Path) -> dict:
    row: dict = {"name": path.stem}
    try:
        graph, meta = load(directory, path.stem)
        row["description"] = meta.get("description", "")
        row["params"] = sorted(discover(graph, meta))
    except (WorkflowError, json.JSONDecodeError) as exc:
        row["error"] = str(exc)
    return row
