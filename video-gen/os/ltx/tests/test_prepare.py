"""Weight readiness checks without downloading models."""

from __future__ import annotations

from pathlib import Path

import pytest
from ltx_service import prepare
from safetensors.numpy import save_file


def _write_min_safetensors(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file({"w": __import__("numpy").zeros((1,), dtype="float32")}, path)


def test_ltx25_pack_needs_decode_and_audio_files(tmp_path: Path):
    for name in prepare._required_files(tmp_path):
        _write_min_safetensors(tmp_path / name)
    assert prepare._complete(tmp_path)


def test_ltx_core_files_alone_are_not_complete(tmp_path: Path):
    for name in (
        "transformer-distilled.safetensors",
        "text_encoder.safetensors",
        "spatial_upscaler_x2_v1_0.safetensors",
    ):
        _write_min_safetensors(tmp_path / name)
    assert not prepare._complete(tmp_path)


@pytest.mark.parametrize("size", [0, 8])
def test_ltx_truncated_safetensors_fail(tmp_path: Path, size: int):
    for name in prepare._required_files(tmp_path):
        path = tmp_path / name
        if name == "vocoder.safetensors":
            path.write_bytes(b"\x00" * size)
        else:
            _write_min_safetensors(path)
    assert not prepare._complete(tmp_path)
