"""插件管理页：页签、主从结构、空态与本地化的最小行为契约。"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from sllkgui.guicore import CButton


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


def test_inspector_shows_dependency_state(qapp):
    """缺依赖的插件在详情里给出「缺什么 + 一键补全 + 可复制命令」。"""
    host = QWidget()
    host.runtime = SimpleNamespace(
        manager=_Manager(),
        sources=_Sources(),
        plugin_dependencies=lambda plugin_id: (
            ["mutagen>=1.47", "quickjs>=1.19"],
            ["quickjs>=1.19"],
        ),
        plugin_dependency_command=lambda plugin_id: "uv pip install --python python quickjs>=1.19",
    )
    page = _page(host)
    try:
        record = dict(page._manager().installed_rows()[0])
        record["installed"] = True
        record["installed_version"] = record["version"]
        inspector = page._build_plugin_inspector(record)
        labels = [item.text() for item in inspector.findChildren(QLabel)]
        assert page.ctx.text("detail.dependencies", "依赖") in labels
        assert "mutagen>=1.47" in labels
        assert "quickjs>=1.19" in labels
        assert page.ctx.text("detail.dep_missing", "缺失") in labels
        buttons = [item.text() for item in inspector.findChildren(CButton)]
        assert page.ctx.text("detail.deps_complete", "补全依赖") in buttons
        assert page.ctx.text("detail.deps_copy", "复制安装命令") in buttons
    finally:
        page.deleteLater()
        host.deleteLater()


def test_busy_state_uses_toast_not_inline_strip(qapp):
    """忙碌反馈改走 toast：页面不再插入会挤动布局的活动条。"""
    from sllkgui.guicore.feedback import toast_bus

    host = QWidget()
    host.resize(900, 600)
    host.show()
    page = _page(host)
    try:
        assert not hasattr(page, "busy_strip")
        page._set_busy(True, "正在安装插件…")
        assert page._busy_toast
        toast_id = page._busy_toast
        page._set_busy(False)
        assert page._busy_toast == ""
        assert str(toast_bus().state_of(toast_id)) == "closed"
    finally:
        page.deleteLater()
        host.deleteLater()


def test_ensure_ready_installs_then_continues(qapp):
    """缺依赖时先补全再继续（安装/启用共用），不要求用户再点一次。"""
    import time

    installed: list[str] = []
    host = QWidget()
    host.resize(900, 600)
    host.show()
    host.runtime = SimpleNamespace(
        manager=_Manager(),
        sources=_Sources(),
        plugin_dependencies=lambda plugin_id: (["demo>=1"], ["demo>=1"]),
        install_plugin_dependencies=lambda plugin_id: installed.append(plugin_id) or ("demo>=1",),
        recent_reloads=lambda limit=5: [],
    )
    page = _page(host)
    try:
        ready: list[str] = []
        page._ensure_ready("com.example.one", then=lambda: ready.append("ready"))
        deadline = time.monotonic() + 5
        while not ready and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.02)
        assert installed == ["com.example.one"]
        assert ready == ["ready"]
    finally:
        page.deleteLater()
        host.deleteLater()
