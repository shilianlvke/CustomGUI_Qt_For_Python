from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.loader import load_plugin, unload_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_context_members(tmp_path: Path, app):
    root = write_plugin(tmp_path / "hello")
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    registry = GalleryRegistry()
    record = load_plugin(root, store, registry, parent_window=lambda: "window", open_surface=lambda pid, sid: True)
    assert record is not None
    ctx = record.context
    assert ctx.plugin_id == "com.example.hello"
    assert ctx.plugin_version == "1.0.0"
    assert ctx.data_dir.is_dir()
    assert ctx.cache_dir.is_dir()
    assert ctx.locale
    assert ctx.theme
    assert [item.value for item in ctx.permissions] == ["filesystem.write"]
    assert ctx.resource("icon", "home.svg").is_file()
    assert ctx.text("home.title", "fallback") in {"首页", "Home"}
    assert ctx.text("missing.key", "fallback") == "fallback"
    assert ctx.open_surface("home") is True
    assert ctx.parent_window() == "window"
    ctx.log("hello", "debug")
    ctx.logger.info("bridged")
    ctx.event("ctx.test", {"value": 1})
    with ctx.timing("ctx.timing"):
        pass
    ctx.report_error("HELLO_FAILED", "boom", "detail")
    assert record.telemetry_seen is True
    with pytest.raises(GalleryError):
        ctx.resource("..", "escape.txt")
    unload_plugin(record)
