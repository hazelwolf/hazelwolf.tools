import os
from pathlib import Path

import pytest
from localbox_tool import core


@pytest.fixture
def dest(tmp_path, monkeypatch):
    folder = tmp_path / "comfy"
    other = tmp_path / "other"
    monkeypatch.setenv("LOCALBOX_DESTINATIONS", f"comfy={folder},extra={other}")
    monkeypatch.setenv("LOCALBOX_MAX_MB", "1")
    return folder


def test_default_tag_and_rows(dest):
    assert core.default_tag() == "comfy"
    rows = core.destination_rows()
    assert rows[0]["tag"] == "comfy"
    assert rows[0]["default"] is True
    assert rows[0]["path"] == str(dest)


def test_save_stream_keeps_name_then_suffixes(dest):
    first = core.save_stream("comfy", "shot.PNG", _bytes(b"png-a"))
    second = core.save_stream("comfy", "shot.PNG", _bytes(b"png-b"))
    assert Path(first["path"]).name == "shot.png"
    assert Path(second["path"]).name == "shot-2.png"
    assert Path(first["path"]).read_bytes() == b"png-a"
    assert first["tag"] == "comfy"
    assert first["bytes"] == 5


def test_strips_directory_from_filename(dest):
    saved = core.save_stream("comfy", "../../etc/passwd.png", _bytes(b"ok"))
    assert Path(saved["path"]).parent == dest
    assert Path(saved["path"]).name == "passwd.png"


def test_rejects_bad_type_and_empty(dest):
    with pytest.raises(core.LocalboxError):
        core.save_stream("comfy", "notes.txt", _bytes(b"hi"))
    with pytest.raises(core.LocalboxError):
        core.save_stream("comfy", "empty.png", _bytes(b""))


def test_rejects_unknown_tag(dest):
    with pytest.raises(core.LocalboxError, match="Unknown destination"):
        core.save_stream("nope", "a.png", _bytes(b"x"))


def test_rejects_oversize(dest, monkeypatch):
    monkeypatch.setenv("LOCALBOX_MAX_MB", "1")
    with pytest.raises(core.LocalboxError, match="exceeds"):
        core.save_stream("comfy", "big.mp4", _bytes(b"x" * (1024 * 1024 + 1)))
    assert list(dest.glob("*")) == []


def test_save_path_copies_local_file(dest, tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"video")
    saved = core.save_path(None, str(src))
    assert Path(saved["path"]).read_bytes() == b"video"
    assert saved["tag"] == "comfy"
    assert src.exists()


def test_malformed_destinations(monkeypatch):
    monkeypatch.setenv("LOCALBOX_DESTINATIONS", "comfy")
    with pytest.raises(core.LocalboxError, match="tag=path"):
        core.destinations()


def test_relative_destination_resolves_against_workspace(monkeypatch):
    monkeypatch.setenv("LOCALBOX_DESTINATIONS", "comfy=../ComfyUI/input")
    assert core.destinations()["comfy"] == (core.workspace_root() / "../ComfyUI/input").resolve()


class _bytes:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, n=-1):
        if self._pos >= len(self._data):
            return b""
        if n is None or n < 0:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk


def test_omitted_destination_uses_comfy(dest):
    saved = core.save_stream("", "a.webp", _bytes(b"webp"))
    assert saved["tag"] == "comfy"
    assert os.path.dirname(saved["path"]) == str(dest)
