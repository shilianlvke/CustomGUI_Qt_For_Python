"""独立设置窗口：导航、脏值状态与保存落盘（offscreen）。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

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
)
from sllkgui.gallery.settings import PluginSettings
from sllkgui.guicore.window.settings_window import CSettingsWindow


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
                ),
            ),
        )
    )
    session = SettingsSession(registry, store)
    window = CSettingsWindow(None, session=session)
    window.show()
    QApplication.processEvents()
    yield window, session, core, store
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
    assert window.unsaved_badge.isVisible()
    assert "1" in window.action_bar.status_text()

    assert window.save()
    assert core.data["remember_window_size"] is False
    assert not session.is_dirty()
    assert not window.unsaved_badge.isVisible()


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


def test_search_filters_navigation(prepared):
    window, _session, _core, _store = prepared
    window.search.setText("桌面")
    assert window.nav.visible_count() >= 1
    window.search.setText("不存在的设置")
    assert window.nav.visible_count() == 0
    window.search.setText("")
    assert window.nav.visible_count() >= 5
