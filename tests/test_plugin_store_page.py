"""插件管理页：页签、主从结构、空态与本地化的最小行为契约。"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _Manager:
    def __init__(self) -> None:
        self.enabled_calls: list[tuple[str, bool]] = []
        self.update_calls: list[str] = []

    def installed_rows(self):
        return [
            {
                "id": "com.example.one",
                "name": "One",
                "summary": "First plugin",
                "version": "1.2.0",
                "source": "official",
                "repository": "https://example.com/one",
                "commit": "0123456789abcdef",
                "permissions": ["filesystem.write"],
                "compliance": "verified",
                "enabled": True,
                "path": "plugins/com.example.one",
                "previous": {"version": "1.1.0"},
                "icon": "",
            }
        ]

    def search(self, query: str = "", source_id: str = ""):
        return [
            {
                "id": "com.example.two",
                "name": "Two",
                "summary": "Second plugin",
                "version": "2.0.0",
                "source": "official",
                "author": "tester",
                "categories": ["tools"],
                "permissions": [],
                "compliance": "community",
                "repository": "https://example.com/two",
                "icon": "",
            }
        ]

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict:
        self.enabled_calls.append((plugin_id, enabled))
        return {"id": plugin_id, "enabled": enabled, "disabled_dependents": []}

    def update(self, plugin_id: str, **kwargs):
        self.update_calls.append(plugin_id)
        return {"id": plugin_id, "updated": True, "version": "1.3.0"}

    def rollback(self, plugin_id: str, **kwargs):
        return {"id": plugin_id, "version": "1.1.0"}

    def remove(self, plugin_id: str):
        return {}

    def install(self, plugin_id: str, source_id: str = ""):
        return {}


class _Sources:
    def list(self):
        return [
            SimpleNamespace(
                source_id="official",
                url="https://example.com/source.git",
                trust="official",
                enabled=True,
                commit="abcdef012345",
                last_refresh="2026-11-20 10:00",
            )
        ]

    def info(self, source_id: str):
        return SimpleNamespace(name="Official Source", source_id=source_id)

    def add(self, url: str, refresh: bool = True):
        return SimpleNamespace(source_id="custom")

    def refresh(self, source_id: str):
        return None

    def refresh_all(self):
        return None

    def remove(self, source_id: str):
        return None

    def set_enabled(self, source_id: str, enabled: bool) -> None:
        return None


def _page(host: QWidget):
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    page = build_plugin_store_page(host)
    page.resize(1120, 720)
    page.show()
    return page


def test_page_builds_and_switches_modes(qapp):
    host = QWidget()
    page = _page(host)
    try:
        assert page.mode == "installed"
        assert page.mode_tabs.current_index() == 0

        page.switch_mode("sources")
        assert page.mode == "sources"
        assert page.mode_tabs.current_index() == 2
        assert not page.add_source_button.isHidden()

        page.switch_mode("discover")
        assert page.mode == "discover"
        assert page.mode_tabs.current_index() == 1
    finally:
        page.deleteLater()
        host.deleteLater()


def test_empty_page_has_empty_list_and_inspector(qapp):
    host = QWidget()
    page = _page(host)
    try:
        assert page.list_panel.rows() == []
        assert page._counts == {"installed": 0, "discover": 0, "sources": 0}
        assert page.inspector_panel.body_layout.count() >= 1
    finally:
        page.deleteLater()
        host.deleteLater()


def test_rows_and_inspector_follow_runtime(qapp):
    host = QWidget()
    host.runtime = SimpleNamespace(manager=_Manager(), sources=_Sources())
    page = _page(host)
    try:
        rows = page.list_panel.rows()
        assert len(rows) == 1
        assert rows[0].record["id"] == "com.example.one"
        assert page._selection["installed"] == "com.example.one"

        page.switch_mode("discover")
        assert page.mode == "discover"
        assert page._selection["discover"] == "com.example.two"
        record = page._selected_record()
        assert record is not None and record["installed"] is False

        page._set_plugin_enabled("com.example.one", False)
        assert host.runtime.manager.enabled_calls == [("com.example.one", False)]
    finally:
        page.deleteLater()
        host.deleteLater()


def test_inspector_shows_recent_reload_diagnostics(qapp):
    host = QWidget()
    host.runtime = SimpleNamespace(
        manager=_Manager(),
        sources=_Sources(),
        recent_reloads=lambda limit=5: [
            SimpleNamespace(
                ok=True,
                targets=["com.example.one"],
                duration_ms=12.5,
                rollback="none",
                code="",
            )
        ],
    )
    page = _page(host)
    try:
        record = dict(page._manager().installed_rows()[0])
        record["installed"] = True
        record["installed_version"] = record["version"]
        inspector = page._build_plugin_inspector(record)
        labels = [item.text() for item in inspector.findChildren(QLabel)]
        assert page.ctx.text("detail.reload_history", "最近重载") in labels
    finally:
        page.deleteLater()
        host.deleteLater()


def test_row_click_on_title_selects_row(qapp):
    """行内标题不能吞掉点击：QLabel 关闭文字选择后整行仍可选。"""
    from sllkgui.guis.pages.plugin_store.context import PageContext
    from sllkgui.guis.pages.plugin_store.entries import StoreRow

    row = StoreRow(
        {"id": "com.example.one", "name": "One", "summary": "First plugin", "version": "1.0.0", "installed": True},
        "installed",
        PageContext(lambda: None),
    )
    row.show()
    clicked: list[dict] = []
    row.clicked.connect(clicked.append)
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(100, 20))
    assert clicked and clicked[0]["id"] == "com.example.one"
    row.deleteLater()


def test_retranslate_keeps_mode(qapp):
    host = QWidget()
    page = _page(host)
    try:
        page.switch_mode("sources")
        page.retranslate()
        assert page.mode == "sources"
        assert page.mode_tabs.current_index() == 2
    finally:
        page.deleteLater()
        host.deleteLater()


def test_legacy_detail_dialogs_are_removed():
    """详情已改为内嵌检查器，包内不应再有 dialogs 模块。"""
    assert importlib.util.find_spec("sllkgui.guis.pages.plugin_store.dialogs") is None
