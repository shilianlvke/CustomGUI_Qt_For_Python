"""插件管理页：页内操作必须原地完成，不得跳页或整页刷新。

覆盖两类回归：

- 启停 / 更新 / 回滚 / 卸载 / 安装 / 刷新来源完成后，调用的是「停留本页」的
  重载入口，而不是会跳回默认路由的旧入口；
- 页面因插件重载被重建时，模式、搜索词、选中项与列表滚动位置都要恢复。
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget


class _Manager:
    def __init__(self) -> None:
        self.enabled_calls: list[tuple[str, bool]] = []

    def installed_rows(self):
        return [
            {
                "id": f"com.example.p{index}",
                "name": f"Plugin {index}",
                "summary": f"Summary {index}",
                "version": "1.0.0",
                "source": "official",
                "repository": "",
                "commit": "0123456789abcdef",
                "permissions": [],
                "compliance": 1,
                "enabled": index % 2 == 0,
                "path": "",
                "previous": {},
                "icon": "",
            }
            for index in range(12)
        ]

    def search(self, query: str = "", source_id: str = ""):
        return []

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict:
        self.enabled_calls.append((plugin_id, enabled))
        return {"id": plugin_id, "enabled": enabled, "disabled_dependents": []}

    def update(self, plugin_id: str, **kwargs):
        return {"id": plugin_id, "updated": True, "version": "1.1.0"}

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
    """记录重载调用；插件管理页用它判断是否「停留本页」。"""

    def __init__(self) -> None:
        super().__init__()
        self.runtime = SimpleNamespace(manager=_Manager(), sources=_Sources())
        self.reload_calls: list[str] = []
        self.page_object = "page_native_plugin_store"

    def reload_plugins(self, native_page: str = "") -> None:
        self.reload_calls.append(native_page)


class _SelectiveWindow(_Window):
    """支持选择性重载的宿主：记录单插件刷新请求。"""

    def __init__(self) -> None:
        super().__init__()
        self.selective_calls: list[tuple[str, str, bool]] = []

    def reload_plugin_in_place(self, plugin_id: str, *, reason: str = "manual", load: bool = True) -> None:
        self.selective_calls.append((plugin_id, reason, load))


def _page(window: QWidget):
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    page = build_plugin_store_page(window)
    page.setObjectName("page_native_plugin_store")
    page.resize(1120, 720)
    page.show()
    return page


def _drain(qapp) -> None:
    """执行排队中的 single_shot 回调（重载是延迟 120ms 触发的）。"""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    loop = QEventLoop()
    QDeadlineTimer(600)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(400, loop.quit)
    loop.exec()


def test_enable_stays_on_page(qapp):
    """启用/停用后必须请求「停留本页」的重载，且传入本页 page_object。"""
    window = _Window()
    page = _page(window)
    try:
        page._set_plugin_enabled("com.example.p1", True)
        assert window.runtime.manager.enabled_calls == [("com.example.p1", True)]
        _drain(qapp)
        assert window.reload_calls == ["page_native_plugin_store"]
    finally:
        page.deleteLater()
        window.deleteLater()


def test_row_toggle_stays_on_page(qapp):
    window = _Window()
    page = _page(window)
    try:
        page._on_row_toggled("com.example.p2", False)
        _drain(qapp)
        assert window.reload_calls == ["page_native_plugin_store"]
    finally:
        page.deleteLater()
        window.deleteLater()


def test_update_and_rollback_stay_on_page(qapp):
    window = _Window()
    page = _page(window)
    try:
        page._update_plugin("com.example.p0")
        _drain(qapp)
        assert window.reload_calls == ["page_native_plugin_store"]

        page._busy = False
        page._rollback_plugin("com.example.p0")
        _drain(qapp)
        assert window.reload_calls == ["page_native_plugin_store"] * 2
    finally:
        page.deleteLater()
        window.deleteLater()


def test_refresh_does_not_reload_runtime(qapp):
    """「刷新」只重读列表，不得触发插件重载（那会重建页面）。"""
    window = _Window()
    page = _page(window)
    try:
        page._refresh_installed()
        _drain(qapp)
        assert window.reload_calls == []
        assert page._counts["installed"] == 12
    finally:
        page.deleteLater()
        window.deleteLater()


def test_source_refresh_does_not_reload_runtime(qapp):
    window = _Window()
    page = _page(window)
    try:
        page._refresh_sources()
        _drain(qapp)
        assert window.reload_calls == []
    finally:
        page.deleteLater()
        window.deleteLater()


def test_state_survives_rebuild(qapp):
    """重建前保存的模式 / 搜索 / 选中，要在新页面上恢复。"""
    window = _Window()
    page = _page(window)
    try:
        page.switch_mode("discover")
        page.search.setText("plug")
        page._apply_search()
        page._selection["discover"] = "com.example.two"

        page._stash_state(window)
        page.deleteLater()

        rebuilt = _page(window)
        try:
            assert rebuilt.mode == "discover"
            assert rebuilt.query == "plug"
            assert rebuilt.search.text() == "plug"
            assert rebuilt._selection["discover"] == "com.example.two"
        finally:
            rebuilt.deleteLater()
    finally:
        window.deleteLater()


def test_state_is_consumed_once(qapp):
    """状态只恢复一次：再次构建页面不再套用旧状态。"""
    window = _Window()
    page = _page(window)
    try:
        page.switch_mode("sources")
        page._stash_state(window)
        page.deleteLater()

        first = _page(window)
        try:
            assert first.mode == "sources"
            assert getattr(window, first._STATE_ATTR, None) is None
        finally:
            first.deleteLater()

        second = _page(window)
        try:
            assert second.mode == "installed"
        finally:
            second.deleteLater()
    finally:
        window.deleteLater()


def test_filter_is_preserved_within_mode_switch(qapp):
    """同一页签内重复进入不应清空用户搜索词（重建恢复路径）。"""
    window = _Window()
    page = _page(window)
    try:
        page.search.setText("Plugin 1")
        page._apply_search()
        assert page.query == "Plugin 1"

        page._switch_mode("installed", reset_query=False)
        assert page.query == "Plugin 1"
        assert page.search.text() == "Plugin 1"
    finally:
        page.deleteLater()
        window.deleteLater()


def test_switch_mode_still_clears_search(qapp):
    """用户主动切页签仍沿用原语义：清空搜索。"""
    window = _Window()
    page = _page(window)
    try:
        page.search.setText("abc")
        page._apply_search()
        page.switch_mode("sources")
        assert page.query == ""
        assert page.search.text() == ""
    finally:
        page.deleteLater()
        window.deleteLater()


def test_selective_host_gets_plugin_id_and_load_flag(qapp):
    """宿主实现 reload_plugin_in_place 时，不再走全量重载。"""
    window = _SelectiveWindow()
    page = _page(window)
    try:
        page._set_plugin_enabled("com.example.p1", True)
        page._set_plugin_enabled("com.example.p2", False)
        _drain(qapp)
        assert set(window.selective_calls) == {
            ("com.example.p1", "enable", True),
            ("com.example.p2", "disable", False),
        }
        assert window.reload_calls == []
    finally:
        page.deleteLater()
        window.deleteLater()


def test_selective_host_update_and_rollback(qapp):
    window = _SelectiveWindow()
    page = _page(window)
    try:
        page._update_plugin("com.example.p0")
        _drain(qapp)
        page._busy = False
        page._rollback_plugin("com.example.p0")
        _drain(qapp)
        assert window.selective_calls == [
            ("com.example.p0", "update", True),
            ("com.example.p0", "rollback", True),
        ]
        assert window.reload_calls == []
    finally:
        page.deleteLater()
        window.deleteLater()


def test_selective_host_install_and_remove(qapp, monkeypatch):
    from sllkgui.guicore import CConfirmDialog

    monkeypatch.setattr(CConfirmDialog, "ask", staticmethod(lambda *args, **kwargs: True))
    window = _SelectiveWindow()
    page = _page(window)
    try:
        page._install_plugin({"id": "com.example.two", "name": "Two", "source": "official"})
        _drain(qapp)
        page._remove_plugin("com.example.one")
        _drain(qapp)
        assert window.selective_calls == [
            ("com.example.two", "install", True),
            ("com.example.one", "remove", False),
        ]
        assert window.reload_calls == []
    finally:
        page.deleteLater()
        window.deleteLater()
