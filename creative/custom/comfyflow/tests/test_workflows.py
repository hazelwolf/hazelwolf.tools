import pytest
from comfyflow_tool import workflows as wf
from comfyflow_tool.errors import NotFound, WorkflowError


def graph():
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a fox", "clip": ["9", 0]},
            "_meta": {"title": "@prompt"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"seed": 1, "steps": 8, "cfg": 1.0, "positive": ["1", 0], "negative": ["3", 0]},
            "_meta": {"title": "@sampler"},
        },
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["9", 0]}, "_meta": {"title": "Negative"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "a.png"}, "_meta": {"title": "@image"}},
        "5": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "x", "images": ["2", 0]},
            "_meta": {"title": "Save"},
        },
    }


def test_discover_names_and_types():
    found = wf.discover(graph())
    assert set(found) == {"prompt", "sampler.seed", "sampler.steps", "sampler.cfg", "image"}
    assert found["image"].type == "file"
    assert found["sampler.cfg"].type == "number"
    assert found["sampler.steps"].type == "integer"


def test_apply_coerces_and_randomizes_seed_unless_given():
    g = graph()
    found = wf.discover(g)
    out, seeds = wf.apply_params(g, found, {"prompt": "a cat", "sampler.steps": "4"})
    assert out["1"]["inputs"]["text"] == "a cat"
    assert out["2"]["inputs"]["steps"] == 4
    assert out["2"]["inputs"]["seed"] == seeds["sampler.seed"] != 1
    assert g["2"]["inputs"]["seed"] == 1  # input graph untouched
    out, seeds = wf.apply_params(g, found, {"sampler.seed": 7})
    assert out["2"]["inputs"]["seed"] == 7 and seeds == {"sampler.seed": 7}
    out, _ = wf.apply_params(g, found, {}, randomize_seed=False)
    assert out["2"]["inputs"]["seed"] == 1


def test_raw_target_and_errors():
    g = graph()
    found = wf.discover(g)
    out, _ = wf.apply_params(g, found, {"3.text": "ugly"})
    assert out["3"]["inputs"]["text"] == "ugly"
    with pytest.raises(WorkflowError, match="Exposed parameters"):
        wf.apply_params(g, found, {"nope": 1})
    with pytest.raises(WorkflowError, match="wired"):
        wf.apply_params(g, found, {"1.clip": "x"})
    with pytest.raises(WorkflowError, match="integer"):
        wf.apply_params(g, found, {"sampler.steps": "many"})


def test_duplicate_param_names_rejected():
    g = graph()
    g["3"]["_meta"]["title"] = "@prompt"
    with pytest.raises(WorkflowError, match="unique"):
        wf.discover(g)


def test_scaffold_titles():
    g = graph()
    for node in g.values():
        node["_meta"]["title"] = node["class_type"]
    g["6"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1, "height": 1, "batch_size": 1}}
    g["7"] = {"class_type": "PrimitiveInt", "inputs": {"value": 5}, "_meta": {"title": "Frame Rate"}}
    g["8"] = {
        "class_type": "EmptyLTXVLatentVideo",
        "inputs": {"width": ["1", 0], "height": ["1", 0], "batch_size": 1},
        "_meta": {"title": "Latent"},
    }
    out = wf.scaffold_titles(g)
    assert out["8"]["_meta"]["title"] == "Latent"  # wired width/height: not a size node
    titles = {k: v["_meta"]["title"] for k, v in out.items()}
    assert titles["1"] == "@prompt" and titles["3"] == "@negative_prompt"
    assert titles["2"] == "@sampler" and titles["4"] == "@image"
    assert titles["6"] == "@size" and titles["7"] == "@frame_rate"
    assert titles["5"] == "SaveImage"


def test_load_save_roundtrip_and_ui_format_rejected(tmp_path):
    wf.save(tmp_path, "demo", graph(), {"description": "d"})
    loaded, meta = wf.load(tmp_path, "demo")
    assert meta["description"] == "d" and "_comfyflow" not in loaded
    with pytest.raises(WorkflowError, match="already exists"):
        wf.save(tmp_path, "demo", graph(), {})
    (tmp_path / "ui.json").write_text('{"nodes": [], "links": []}')
    with pytest.raises(WorkflowError, match="not API format"):
        wf.load(tmp_path, "ui")
    with pytest.raises(NotFound):
        wf.load(tmp_path, "missing")
    with pytest.raises(WorkflowError):
        wf.load(tmp_path, "../etc")
