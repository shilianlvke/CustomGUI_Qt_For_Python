from __future__ import annotations

import sys
from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery.loader import load_plugin, unload_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> GalleryStore:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return store


def test_load_plugin_and_context(tmp_path: Path, app):
    root = write_plugin(tmp_path / "hello")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    assert record.plugin_id == "com.example.hello"
    assert registry.surface_count() == 1
    route = registry.default_route()
    assert route == "com.example.hello/home"
    surface = registry.get(route)
    assert surface.plugin.context.text("home.title", "?") in {"首页", "Home"}
    widget = surface.factory(surface.plugin.context)
    assert widget is not None
    unload_plugin(record)


def test_missing_plugin_export_is_isolated(tmp_path: Path):
    root = write_plugin(tmp_path / "bad", plugin_source="VALUE = 1\n")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is None
    assert registry.surface_count() == 0
    assert any(item["code"] == "PLUGIN_LOAD_FAILED" for item in registry.errors)


def test_duplicate_plugin_skipped(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    store = _store(tmp_path)
    registry = GalleryRegistry()
    assert load_plugin(root, store, registry) is not None
    assert load_plugin(root, store, registry) is None


def test_unload_purges_modules_imported_from_plugin_root(tmp_path: Path):
    """插件仓库内的顶层包必须随卸载清理，否则更新后仍命中旧模块。"""
    helper_name = "gallery_test_helper_pkg"
    root = write_plugin(tmp_path / "hello")
    helper = root / helper_name
    helper.mkdir()
    (helper / "__init__.py").write_text("VALUE = 'v1'\n", encoding="utf-8")
    source = (root / "plugin.py").read_text(encoding="utf-8")
    (root / "plugin.py").write_text(
        f"{source}\nimport {helper_name}\n\nHELPER_VALUE = {helper_name}.VALUE\n",
        encoding="utf-8",
    )

    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    assert sys.modules[helper_name].VALUE == "v1"

    unload_plugin(record)
    assert helper_name not in sys.modules

    # 模拟插件更新：同一路径换成新代码后重载，应读到新模块而不是缓存
    (helper / "__init__.py").write_text("VALUE = 'v2'\nUPDATED = True\n", encoding="utf-8")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    assert sys.modules[helper_name].VALUE == "v2"
    unload_plugin(record)
