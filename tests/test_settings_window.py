"""独立设置窗口：导航、脏值状态与保存落盘（offscreen）。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow

from sllkgui.appcore import (
    AppLanguages,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    Setting,
    SettingsPage,
    SettingsRegistry,
    SettingsSection,
    SettingsSession,
    SettingsStore,
    ensure_core_pages,
    get_app_context,
    plugin_namespace,
    settings_page_bus,
)
from sllkgui.gallery.settings import PluginSettings
from sllkgui.guicore import CActionRow
from sllkgui.guicore.window.settings_window import CSettingsWindow

_ACTION_CALLS: list[int] = []


class _MemoryCore:
    def __init__(self) -> None:
        self.data: dict = {}

    def load(self) -> dict:
        return dict(self.data)

    def save(self, updates) -> bool:
        self.data.update(dict(updates))
        return True

    def path(self) -> Path:
        return Path("user.yaml")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def prepared(qapp, tmp_path):
    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)
    core = _MemoryCore()
    registry = SettingsRegistry()
    ensure_core_pages(registry)
    store = SettingsStore(settings_dir=tmp_path, core=core)
    bridge = PluginSettings("com.example.window", registry=registry, store=store)
    _ACTION_CALLS.clear()
    bridge.define(
        SettingsPage(
            page_id="desktop",
            title="桌面整理",
            sections=(
                SettingsSection(
                    "behavior",
                    (
                        Setting.switch("auto_refresh", True, "自动刷新"),
                        Setting.number("columns", 4, "列数", minimum=1, maximum=12),
                    ),
                    info=(Setting.info("stats", "执行次数", lambda: f"{len(_ACTION_CALLS)} 次"),),
                    actions=(
                        Setting.action(
                            "ping",
                            "刷新统计",
                            lambda: _ACTION_CALLS.append(1),
                            button="执行",
                        ),
                    ),
                ),
            ),
        )
    )
    session = SettingsSession(registry, store)
    window = CSettingsWindow(None, session=session)
    window.show()
    QApplication.processEvents()
    yield window, session, core, store
    # 失败路径先丢弃草稿，避免关闭时弹出模态确认框卡住测试
    session.discard()
    window._detach_page_bus()
    window.close()
    window.deleteLater()


def test_window_navigation_covers_core_and_plugins(prepared):
    window, _session, _core, _store = prepared
    ids = window.nav.item_ids()
    assert {"appearance", "interface", "window", "__shortcuts__", "__about__"} <= set(ids)
    plugin_items = [item for item in ids if item.startswith("plugin::")]
    assert plugin_items == ["plugin::com.example.window::desktop"]

    assert window.show_page("interface")
    assert window.page_title.text() == "界面"
    assert window.show_page(plugin_items[0])
    assert window.page_title.text() == "桌面整理"
    assert not window.show_page("missing")


def test_dirty_state_and_save_persist(prepared):
    window, session, core, _store = prepared
    key = "core.window.remember_size"
    session.set(key, False)
    window.notify_modified()

    assert window.action_bar.isVisible()
    assert "1" in window.action_bar.status_text()

    assert window.save()
    assert core.data["remember_window_size"] is False
    assert not session.is_dirty()
    assert window.save(), "no pending changes should save as a no-op"


def test_appearance_has_theme_cards_without_dark_mode_toggle(prepared):
    window, _session, _core, _store = prepared
    assert window.show_page("appearance")
    view = window._entries["appearance"]["view"]
    assert {card.name() for card in view._theme_cards} == set(AppThemes)
    assert "__dark_mode__" not in view._rows
    assert all("深色模式" not in row._title.text() for row in view._rows.values())


def test_refresh_language_keeps_current_page_and_window(prepared):
    from sllkgui.guis.language_service import apply_language

    window, _session, _core, _store = prepared
    assert window.show_page("interface")
    assert window.page_title.text() == "界面"
    try:
        apply_language("en_us")
        window.refresh_language()
        assert window.isVisible()
        assert window.current_page_id() == "interface"
        assert window.page_title.text() == "Interface"
    finally:
        apply_language("zh_cn")
        window.refresh_language()


def test_reset_buttons_stay_visible_and_disable_at_default(prepared):
    window, session, _core, _store = prepared
    window.show_page("appearance")
    view = window._entries["appearance"]["view"]
    for key, row in view._rows.items():
        if not row._resettable:
            continue
        assert not row._reset.isHidden(), key
        assert row._reset.isEnabled() == (not session.is_default(key)), key

    key = "core.appearance.transparency"
    default = session.value(key)
    changed = 90 if default != 90 else 10
    view._commit(key, changed)
    assert session.value(key) == changed
    assert view._rows[key]._reset.isEnabled()
    view._rows[key]._reset.click()
    assert session.value(key) == default
    assert not view._rows[key]._reset.isEnabled()


def test_discard_restores_baseline(prepared):
    window, session, _core, _store = prepared
    window.show_page("appearance")
    session.set("core.appearance.theme", "eye")
    window.notify_modified()
    assert window.action_bar.isVisible()

    window.discard()
    assert session.value("core.appearance.theme") == "default"
    assert not session.is_dirty()
    assert not window.action_bar.isVisible()


def test_plugin_settings_save_writes_plugin_file(prepared):
    window, session, _core, store = prepared
    session.set("plugin.com.example.window.columns", 6)
    window.notify_modified()
    assert window.save()

    path = store.path_for("plugin.com.example.window")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "columns: 6" in text
    assert "com.example.window" in text


def test_inline_validation_error_survives_sync(prepared):
    window, session, _core, _store = prepared
    window.show_page("appearance")
    view = window._entries["appearance"]["view"]
    view._commit("core.appearance.transparency", 999)
    row = view._rows["core.appearance.transparency"]
    assert "不能大于" in row.error()
    assert window.action_bar.isVisible()
    assert not session.is_dirty()


def test_window_size_is_eighty_percent_of_host(prepared):
    _window, session, _core, _store = prepared
    host = QMainWindow()
    host.resize(1200, 800)
    host.show()
    QApplication.processEvents()
    window = CSettingsWindow(host, session=SettingsSession(session.registry, session.store), host=host)
    window.open_settings()
    QApplication.processEvents()
    assert (window.width(), window.height()) == (960, 640)

    host.resize(1400, 900)
    QTest.qWait(50)
    assert (window.width(), window.height()) == (1120, 720)
    window.close()
    host.close()
    host.deleteLater()


def test_search_filters_navigation(prepared):
    window, _session, _core, _store = prepared
    window.search.setText("桌面")
    assert window.nav.visible_count() >= 1
    window.search.setText("不存在的设置")
    assert window.nav.visible_count() == 0
    window.search.setText("")
    assert window.nav.visible_count() >= 5


def test_action_row_runs_command_and_info_refreshes(prepared):
    window, _session, _core, _store = prepared
    item_id = "plugin::com.example.window::desktop"
    assert window.show_page(item_id)
    view = window._entries[item_id]["view"]

    info_row, _info = view._info_rows[0]
    assert info_row.value() == "0 次"
    action_row = next(row for row in view._groups[0].rows() if isinstance(row, CActionRow))
    action_row.button().click()
    assert _ACTION_CALLS == [1]

    view.refresh_info()
    assert info_row.value() == "1 次"


def test_plugin_refresh_prunes_removed_draft_keys(prepared):
    """插件更新删掉设置键时，旧草稿必须被清理，不能让保存路径踩空。"""
    window, session, _core, _store = prepared
    item_id = "plugin::com.example.window::desktop"
    assert window.show_page(item_id)
    namespace = plugin_namespace("com.example.window")
    key = f"{namespace}.columns"
    session.set(key, 8)
    assert key in session.dirty_keys()

    registry = session.registry
    registry.unregister_namespace(namespace)
    registry.register(
        SettingsPage(
            page_id="desktop",
            title="桌面整理",
            sections=(
                SettingsSection(
                    "behavior",
                    (Setting.switch("auto_refresh", True, "自动刷新"),),
                ),
            ),
        ),
        namespace=namespace,
        replace=True,
    )
    window._rebuild_plugin_page(namespace)
    QApplication.processEvents()
    assert key not in session.dirty_keys()


def test_plugin_refresh_rebuilds_page_and_keeps_draft(prepared):
    window, session, _core, _store = prepared
    item_id = "plugin::com.example.window::desktop"
    assert window.show_page(item_id)
    key = "plugin.com.example.window.columns"
    session.set(key, 8)
    window.notify_modified()

    _ACTION_CALLS.append(1)
    settings_page_bus().notify("plugin.com.example.window")
    QTest.qWait(20)
    QApplication.processEvents()

    assert window.current_page_id() == item_id
    assert session.value(key) == 8, "重建页面不能丢弃未保存草稿"
    view = window._entries[item_id]["view"]
    assert view._info_rows[0][0].value() == "1 次"
