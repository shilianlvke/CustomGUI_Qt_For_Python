"""插件管理页：操作后就地更新，列表/详情不重建、滚动位置不跳动。"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _Manager:
    def __init__(self) -> None:
        self.enabled_calls: list[tuple[str, bool]] = []
        self.update_calls: list[str] = []
        self.fail_toggle = False
        self.version = "1.0.0"
        self.enabled = {f"com.example.p{index}": index % 2 == 0 for index in range(12)}

    def installed_rows(self):
        return [
            {
                "id": f"com.example.p{index}",
                "name": f"Plugin {index}",
                "summary": f"Summary {index}",
                "version": self.version if index == 0 else "1.0.0",
                "source": "official",
                "repository": "",
                "commit": "0123456789abcdef",
                "permissions": [],
                "compliance": 1,
                "enabled": self.enabled[f"com.example.p{index}"],
                "path": "",
                "previous": {"version": "0.9.0"} if index == 0 else {},
                "icon": "",
            }
            for index in range(12)
        ]

    def search(self, query: str = "", source_id: str = ""):
        return []

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict:
        if self.fail_toggle:
            raise RuntimeError("toggle failed")
        self.enabled_calls.append((plugin_id, enabled))
        self.enabled[plugin_id] = enabled
        return {"id": plugin_id, "enabled": enabled, "disabled_dependents": []}

    def update(self, plugin_id: str, **kwargs):
        self.update_calls.append(plugin_id)
        self.version = "1.1.0"
        return {"id": plugin_id, "updated": True, "version": self.version}

    def rollback(self, plugin_id: str, **kwargs):
        return {"id": plugin_id, "version": "0.9.0"}

    def remove(self, plugin_id: str):
        return {}

    def install(self, plugin_id: str, source_id: str = ""):
        return {}


class _Sources:
    def list(self):
        return []

    def info(self, source_id: str):
        return SimpleNamespace(name=source_id)

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


class _Window(QWidget):
    """支持选择性重载的宿主：任何页面重建/跳页都会记录在案。"""

    def __init__(self) -> None:
        super().__init__()
        self.runtime = SimpleNamespace(manager=_Manager(), sources=_Sources())
        self.selective_calls: list[tuple[str, str, bool]] = []
        self.full_reloads: list[str] = []
        self.page_object = "page_native_plugin_store"

    def reload_plugin_in_place(self, plugin_id: str, *, reason: str = "manual", load: bool = True) -> None:
        self.selective_calls.append((plugin_id, reason, load))

    def reload_plugins(self, native_page: str = "") -> None:
        self.full_reloads.append(native_page)


def _page(window: QWidget):
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    page = build_plugin_store_page(window)
    page.setObjectName(window.page_object)
    page.resize(1120, 720)
    page.show()
    return page


def _wait_until(qapp, predicate, timeout_ms: int = 2000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


def _row(page, plugin_id: str):
    return next(row for row in page.list_panel.rows() if row.record.get("id") == plugin_id)


def test_refresh_all_reuses_rows_and_inspector(qapp):
    """重复刷新不得销毁行/详情控件（这是闪烁的根源）。"""
    window = _Window()
    page = _page(window)
    try:
        qapp.processEvents()
        rows = page.list_panel.rows()
        content = page.inspector_panel.content()
        assert rows and content is not None

        page.refresh_all()
        qapp.processEvents()

        assert page.list_panel.rows() == rows
        assert all(a is b for a, b in zip(page.list_panel.rows(), rows, strict=True))
        assert page.inspector_panel.content() is content
        assert window.full_reloads == []
    finally:
        page.deleteLater()
        window.deleteLater()


def test_toggle_updates_only_target_row_and_state_chip(qapp):
    """启停后：其余行、详情容器与滚动条都保持原对象，只更新开关与状态片。"""
    window = _Window()
    page = _page(window)
    try:
        qapp.processEvents()
        row = _row(page, "com.example.p1")
        page._on_row_clicked(row.record)
        qapp.processEvents()

        rows_before = page.list_panel.rows()
        content_before = page.inspector_panel.content()
        chip_before = page._inspector_state_chip
        toggle_before = page._inspector_toggle_button
        bar = page.list_panel.scroll.verticalScrollBar()
        assert bar.maximum() > 120
        bar.setValue(120)

        page._set_plugin_enabled("com.example.p1", True)
        qapp.processEvents()
        assert _wait_until(qapp, lambda: bool(window.selective_calls))

        assert window.selective_calls == [("com.example.p1", "enable", True)]
        assert window.full_reloads == []
        assert page.list_panel.rows() == rows_before
        assert all(a is b for a, b in zip(page.list_panel.rows(), rows_before, strict=True))
        assert page.inspector_panel.content() is content_before
        assert page._inspector_state_chip is chip_before
        assert page._inspector_toggle_button is toggle_before
        assert chip_before.text() == page.ctx.text("installed.enabled", "已启用")
        assert toggle_before.text() == page.ctx.text("installed.disable", "停用")
        assert row._switch.isChecked() is True
        assert row.record["enabled"] is True
        assert bar.value() == 120
    finally:
        page.deleteLater()
        window.deleteLater()


def test_toggle_failure_reverts_and_keeps_view(qapp):
    """启停失败：开关回到真实状态，列表/详情/滚动不变，同时记录错误。"""
    window = _Window()
    manager = window.runtime.manager
    page = _page(window)
    try:
        qapp.processEvents()
        row = _row(page, "com.example.p1")
        page._on_row_clicked(row.record)
        qapp.processEvents()

        rows_before = page.list_panel.rows()
        content_before = page.inspector_panel.content()
        chip_before = page._inspector_state_chip
        bar = page.list_panel.scroll.verticalScrollBar()
        bar.setValue(120)

        manager.fail_toggle = True
        # 模拟用户拨动开关：失败后必须拨回去，而不是停在错误状态。
        row._switch.setChecked(True)
        qapp.processEvents()

        assert row._switch.isChecked() is False
        assert row.record["enabled"] is False
        assert page.list_panel.rows() == rows_before
        assert all(a is b for a, b in zip(page.list_panel.rows(), rows_before, strict=True))
        assert page.inspector_panel.content() is content_before
        assert page._inspector_state_chip is chip_before
        assert chip_before.text() == page.ctx.text("installed.disabled", "已停用")
        assert bar.value() == 120
        assert getattr(window.runtime, "last_error", {}).get("code") == "PLUGIN_STORE_TOGGLE_FAILED"
        assert window.selective_calls == []
        assert window.full_reloads == []
    finally:
        page.deleteLater()
        window.deleteLater()


def test_update_keeps_unaffected_rows_and_scroll(qapp):
    """更新只替换目标行/详情内容，其余行对象与列表滚动位置保持不变。"""
    window = _Window()
    manager = window.runtime.manager
    page = _page(window)
    try:
        qapp.processEvents()
        rows_before = page.list_panel.rows()
        others = [row for row in rows_before if row.record.get("id") != "com.example.p0"]
        bar = page.list_panel.scroll.verticalScrollBar()
        bar.setValue(120)

        page._update_plugin("com.example.p0")
        assert _wait_until(
            qapp,
            lambda: manager.update_calls and bool(window.selective_calls),
        )

        assert manager.update_calls == ["com.example.p0"]
        assert window.full_reloads == []
        current = page.list_panel.rows()
        assert len(current) == len(rows_before)
        by_id = {row.record.get("id"): row for row in current}
        for row in others:
            assert by_id[row.record["id"]] is row
        assert by_id["com.example.p0"].record["version"] == "1.1.0"
        assert bar.value() == 120
    finally:
        page.deleteLater()
        window.deleteLater()
