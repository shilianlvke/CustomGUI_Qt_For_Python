"""Surface 声明与实现的一致性：加载期失败，而不是点击时才发现空白页。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.gallery.errors import PLUGIN_PATH_ESCAPE, PLUGIN_SURFACE_IMPL_MISSING, GalleryError
from sllkgui.gallery.loader import load_plugin
from sllkgui.gallery.manifest import load_manifest
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.scaffold import scaffold_plugin
from sllkgui.gallery.store import GalleryStore


def test_missing_impl_blocks_load_before_on_load(tmp_path: Path):
    root = scaffold_plugin(tmp_path / "sample", plugin_id="com.example.sample", name="Sample")
    (root / "pages" / "home.py").unlink()

    registry = GalleryRegistry()
    record = load_plugin(root, GalleryStore(tmp_path / "gallery"), registry)

    assert record is None
    codes = [error["code"] for error in registry.errors]
    assert PLUGIN_SURFACE_IMPL_MISSING in codes
    assert not registry.plugins()


def test_impl_path_escape_is_rejected_by_manifest(tmp_path: Path):
    root = scaffold_plugin(tmp_path / "sample", plugin_id="com.example.sample", name="Sample")
    manifest_path = root / "sllkgui-plugin.yml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "impl: pages/home.py", "impl: ../outside.py"
        ),
        encoding="utf-8",
    )

    with pytest.raises(GalleryError) as excinfo:
        load_manifest(root)
    assert excinfo.value.code == PLUGIN_PATH_ESCAPE
