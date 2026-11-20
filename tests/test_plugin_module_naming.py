"""内置插件用规范模块名加载，用户插件仍用隔离别名（RV-11 回归）。"""

from __future__ import annotations

from pathlib import Path

from sllkgui.gallery.loader import _canonical_module_name


def test_showcase_plugin_uses_canonical_module_name():
    root = Path("D:/repo/src/sllkgui/showcase/core_preview")
    entry = root / "plugin.py"
    assert _canonical_module_name(root, entry) == "sllkgui.showcase.core_preview.plugin"


def test_user_plugin_under_similar_path_keeps_alias():
    """路径中出现 sllkgui 但不在 showcase 下时不得误判为内置插件。"""
    root = Path("D:/repo/src/sllkgui/plugins/my_plugin")
    entry = root / "plugin.py"
    assert _canonical_module_name(root, entry) is None


def test_plugin_outside_package_keeps_alias():
    root = Path("D:/repos/my-plugin")
    entry = root / "plugin.py"
    assert _canonical_module_name(root, entry) is None
