"""Weight readiness checks without downloading models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from safetensors.numpy import save_file
from wan_service import prepare


def _write_min_safetensors(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file({"w": __import__("numpy").zeros((1,), dtype="float32")}, path)


def test_wan_complete_requires_index_shards_and_vae(tmp_path: Path):
    for sub in ("transformer", "text_encoder", "vae"):
        (tmp_path / sub).mkdir()
    for rel in prepare._INDEX_PATHS:
        index_path = tmp_path / rel
        shard_name = "shard.safetensors"
        index_path.write_text(json.dumps({"weight_map": {"layer": shard_name}}), encoding="utf-8")
        _write_min_safetensors(index_path.parent / shard_name)
    _write_min_safetensors(tmp_path / "vae" / "diffusion_pytorch_model.safetensors")
    assert prepare._complete(tmp_path)


def test_wan_index_without_shard_is_incomplete(tmp_path: Path):
    for sub in ("transformer", "text_encoder", "vae"):
        (tmp_path / sub).mkdir()
    (tmp_path / prepare._INDEX_PATHS[0]).write_text(json.dumps({"weight_map": {"a": "missing.safetensors"}}))
    (tmp_path / prepare._INDEX_PATHS[1]).write_text(json.dumps({"weight_map": {"b": "te.safetensors"}}))
    _write_min_safetensors(tmp_path / "text_encoder" / "te.safetensors")
    _write_min_safetensors(tmp_path / "vae" / "vae.safetensors")
    assert not prepare._complete(tmp_path)


@pytest.mark.parametrize("size", [0, 8])
def test_wan_empty_vae_shard_fails(tmp_path: Path, size: int):
    for sub in ("transformer", "text_encoder", "vae"):
        (tmp_path / sub).mkdir()
    for rel in prepare._INDEX_PATHS:
        index_path = tmp_path / rel
        shard_name = "ok.safetensors"
        index_path.write_text(json.dumps({"weight_map": {"x": shard_name}}), encoding="utf-8")
        _write_min_safetensors(index_path.parent / shard_name)
    bad = tmp_path / "vae" / "bad.safetensors"
    bad.write_bytes(b"\x00" * size)
    assert not prepare._complete(tmp_path)
