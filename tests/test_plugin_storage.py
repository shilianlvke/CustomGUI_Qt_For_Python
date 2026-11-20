"""插件契约化存储：声明键读写、原子回退、越界拒绝与 purge 清理。"""

from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery.errors import PLUGIN_PATH_ESCAPE, PLUGIN_STORAGE_KEY_UNDECLARED, GalleryError
from sllkgui.gallery.lint import lint_plugin
from sllkgui.gallery.loader import load_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore

BASE_MANIFEST = """schema: 1
api: 2
id: com.example.storage
name: Storage
version: 1.0.0
description: storage test
entry: plugin.py
requires:
  sllkgui: ">=3.0.0,<4.0.0"
  python: ">=3.12"
surfaces:
  - id: home
    title: {en_us: Home}
    icon: resource/icon/home.svg
data:
  - key: notes_index
    path: data/notes.json
permissions:
  - filesystem.write
"""


def _make_ctx(tmp_path: Path, manifest_text: str = BASE_MANIFEST, *, with_template: bool = False):
    root = write_plugin(tmp_path / "plugin", manifest_text=manifest_text)
    if with_template:
        (root / "data").mkdir(exist_ok=True)
        (root / "data" / "notes.json").write_text('{"count": 1}', encoding="utf-8")
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    record = load_plugin(root, store, GalleryRegistry())
    assert record is not None
    return record, store


def test_storage_roundtrip_and_keys(tmp_path: Path):
    record, _store = _make_ctx(tmp_path)
    ctx = record.context
    assert ctx.storage.keys() == ("notes_index",)
    assert ctx.storage.get("notes_index", {"missing": True}) == {"missing": True}
    assert ctx.storage.set("notes_index", {"count": 3}) is True
    assert ctx.storage.get("notes_index") == {"count": 3}
    assert ctx.storage.path("notes_index") == ctx.data_dir / "notes_index.json"


def test_undeclared_key_rejected(tmp_path: Path):
    record, _store = _make_ctx(tmp_path)
    ctx = record.context
    for call in (
        lambda: ctx.storage.get("undeclared"),
        lambda: ctx.storage.set("undeclared", 1),
        lambda: ctx.storage.delete("undeclared"),
        lambda: ctx.storage.path("undeclared"),
    ):
        with pytest.raises(GalleryError) as exc:
            call()
        assert exc.value.code == PLUGIN_STORAGE_KEY_UNDECLARED


def test_path_escape_rejected(tmp_path: Path):
    evil = BASE_MANIFEST.replace("    path: data/notes.json", "    path: ../outside.json")
    root = write_plugin(tmp_path / "evil", manifest_text=evil)
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    registry = GalleryRegistry()
    assert load_plugin(root, store, registry) is None
    assert PLUGIN_PATH_ESCAPE in [item["code"] for item in registry.errors]


def test_backup_fallback(tmp_path: Path):
    record, _store = _make_ctx(tmp_path)
    ctx = record.context
    assert ctx.storage.set("notes_index", {"v": 1}) is True
    assert ctx.storage.set("notes_index", {"v": 2}) is True
    backup = ctx.data_dir / "notes_index.json.bak"
    assert backup.is_file()
    # 主文件损坏后 get 从 .bak 回退
    (ctx.data_dir / "notes_index.json").write_text("not json", encoding="utf-8")
    assert ctx.storage.get("notes_index") == {"v": 1}


def test_delete_removes_file_and_backup(tmp_path: Path):
    record, _store = _make_ctx(tmp_path)
    ctx = record.context
    ctx.storage.set("notes_index", 1)
    ctx.storage.set("notes_index", 2)
    assert ctx.storage.delete("notes_index") is True
    assert not (ctx.data_dir / "notes_index.json").exists()
    assert not (ctx.data_dir / "notes_index.json.bak").exists()


def test_lint_flags_missing_data_template(tmp_path: Path):
    root = write_plugin(tmp_path / "lint", manifest_text=BASE_MANIFEST)
    report = lint_plugin(root)
    codes = {item.code for item in report.errors}
    assert "DATA_TEMPLATE_NOT_FOUND" in codes


def test_purge_clears_storage_data(tmp_path: Path):
    record, store = _make_ctx(tmp_path)
    ctx = record.context
    ctx.storage.set("notes_index", {"count": 9})
    assert (ctx.data_dir / "notes_index.json").is_file()
    store.purge(record.plugin_id)
    assert not (ctx.data_dir / "notes_index.json").exists()
