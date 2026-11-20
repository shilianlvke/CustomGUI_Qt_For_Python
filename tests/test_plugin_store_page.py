"""插件管理页：结构拆分后的最小行为契约（模式切换与组件收敛）。"""

from __future__ import annotations

import importlib.util
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_page_builds_and_switches_modes(qapp):
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    host = QWidget()
    page = build_plugin_store_page(host)
    page.resize(1120, 720)
    page.show()
    QTest.qWait(20)
    try:
        assert page.mode_nav.item_ids() == ("installed", "discover", "sources")
        assert page.stack.currentWidget() is page.installed_panel

        page.switch_mode("sources")
        assert page.stack.currentWidget() is page.sources_panel
        assert page.mode_nav.current() == "sources"

        page.switch_mode("discover")
        assert page.stack.currentWidget() is page.discover_panel
    finally:
        page.deleteLater()
        host.deleteLater()


def test_mode_badges_follow_counts(qapp):
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    host = QWidget()
    page = build_plugin_store_page(host)
    try:
        page.update_discover_count(7)
        assert page._counts["discover"] == 7
        # 重建导轨后徽标仍取最新计数
        assert page.mode_nav.item_ids() == ("installed", "discover", "sources")
    finally:
        page.deleteLater()
        host.deleteLater()


def test_plugin_and_source_detail_dialogs_open(qapp):
    """点击插件/源条目后详情对话框应能构造并打开（历史 bug: mono 重复传参）。"""
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page
    from sllkgui.guis.pages.plugin_store.dialogs import _PluginDetailDialog, _SourceDetailDialog

    host = QWidget()
    page = build_plugin_store_page(host)
    page.resize(1120, 720)
    page.show()
    try:
        record = {
            "id": "com.example.x",
            "name": "X",
            "summary": "test",
            "version": "1.0.0",
            "permissions": ["filesystem.write"],
            "categories": ["tools"],
            "commit": "0123456789abcdef",
        }
        plugin_dialog = _PluginDetailDialog(page, record, installed=False)
        plugin_dialog.open()
        assert plugin_dialog.dialog.isVisible()

        source_dialog = _SourceDetailDialog(
            page, {"id": "test", "url": "https://example.com/source.git", "trust": "user", "enabled": True}
        )
        source_dialog.open()
        assert source_dialog.dialog.isVisible()
    finally:
        page.deleteLater()
        host.deleteLater()


def test_legacy_widgets_module_is_removed():
    """自绘件已全部上移 guicore：包内不应再有 widgets 模块。"""
    assert importlib.util.find_spec("sllkgui.guis.pages.plugin_store.widgets") is None
