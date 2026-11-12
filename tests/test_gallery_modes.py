from __future__ import annotations

from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.runtime import GalleryRuntime


def test_gallery_mode_ignores_external_plugins(tmp_path: Path):
    data = tmp_path / "data"
    gallery = data / "gallery"
    external = write_plugin(gallery / "plugins" / "com.example.external", plugin_id="com.example.external")
    assert external.is_dir()
    (gallery / "registry.json").write_text('{"schema": 1, "plugins": {}}', encoding="utf-8")

    runtime = GalleryRuntime("gallery", data_dir=data)
    registry = runtime.bootstrap()
    try:
        ids = {record.plugin_id for record in runtime.records}
        assert ids == {"com.sllkgui.showcase.core_preview"}
        assert "com.example.external" not in ids
        assert registry.surface_count() == 10
    finally:
        runtime.shutdown()


def test_run_mode_loads_dev_plugin_only(tmp_path: Path):
    dev = write_plugin(tmp_path / "dev", plugin_id="com.example.dev")
    runtime = GalleryRuntime("run", data_dir=tmp_path / "data", plugin_dirs=[dev])
    registry = runtime.bootstrap()
    try:
        ids = {record.plugin_id for record in runtime.records}
        assert "com.example.dev" in ids
        assert "com.sllkgui.core.store" not in ids
        assert "com.sllkgui.showcase.core_preview" not in ids
        assert registry.surface_count() == 1
    finally:
        runtime.shutdown()


def test_run_safe_mode_loads_no_plugins(tmp_path: Path):
    dev = write_plugin(tmp_path / "dev", plugin_id="com.example.dev")
    runtime = GalleryRuntime("run", data_dir=tmp_path / "data", plugin_dirs=[dev], safe_mode=True)
    try:
        runtime.bootstrap()
        assert runtime.records == []
        assert runtime.registry.surface_count() == 0
    finally:
        runtime.shutdown()
