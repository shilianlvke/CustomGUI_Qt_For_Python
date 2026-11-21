"""二阶段能力：开发目录监听与左菜单增量同步。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from sllkgui.appcore import (
        AppLanguages,
        AppSettings,
        AppThemes,
        ColorPalette,
        Language,
        get_app_context,
    )

    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)
    yield QApplication.instance() or QApplication([])


def test_fingerprint_tree_detects_changes(tmp_path: Path):
    from sllkgui.gallery.dev_watch import fingerprint_tree

    root = tmp_path / "plugin"
    root.mkdir()
    (root / "plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = fingerprint_tree(root)

    time.sleep(0.01)
    (root / "plugin.py").write_text("VALUE = 2\n", encoding="utf-8")
    after = fingerprint_tree(root)
    assert before != after
    assert "plugin.py" in after


def test_dev_watcher_emits_changed(tmp_path: Path, qapp):
    from sllkgui.gallery.dev_watch import DevPluginWatcher

    root = tmp_path / "plugin"
    root.mkdir()
    (root / "plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
    watcher = DevPluginWatcher([root], interval_ms=1000)
    seen: list[str] = []
    watcher.changed.connect(seen.append)
    try:
        watcher.poll()
        assert seen == []
        time.sleep(0.01)
        (root / "plugin.py").write_text("VALUE = 2\n", encoding="utf-8")
        watcher.poll()
        assert seen == [str(root.resolve())]
    finally:
        watcher.stop()
        watcher.deleteLater()


def test_load_run_watch_starts_and_stops_watcher(tmp_path: Path, qapp):
    from gallery_helpers import write_plugin

    from sllkgui.window import load_run

    dev = tmp_path / "dev"
    write_plugin(dev / "a", plugin_id="com.example.a", name="A")
    window = load_run(
        data_dir=tmp_path / "data",
        gallery_dir=tmp_path / "data" / "gallery",
        plugin_dirs=[dev],
        install_missing_deps=False,
        interactive=False,
        check_tools=False,
        watch=True,
    )
    try:
        watcher = getattr(window, "_dev_watcher", None)
        assert watcher is not None
        assert watcher.is_running()
        window._stop_dev_watch()
        assert window._dev_watcher is None
    finally:
        window.runtime.shutdown()
        window.close()
        window.deleteLater()


def test_left_menu_sync_reuses_unchanged_buttons(qapp):
    from sllkgui.guicore.window.left_menu.menu import CLeftMenu

    def item(btn_id: str, text: str, *, top: bool = True) -> dict:
        return {
            "btn_icon": "icon_star_fill",
            "btn_id": btn_id,
            "btn_text": text,
            "btn_tooltip": text,
            "btn_text_fallback": text,
            "show_top": top,
            "is_active": False,
        }

    menu = CLeftMenu(None, None)
    try:
        menu.add_menus([item("btn_a", "A"), item("btn_b", "B")])
        button_a = menu._menu_buttons["btn_a"]
        menu.sync_menus([item("btn_a", "A2"), item("btn_c", "C")])
        assert menu._menu_buttons["btn_a"] is button_a
        assert "btn_b" not in menu._menu_buttons
        assert "btn_c" in menu._menu_buttons
        assert menu._menu_lang_keys["btn_a"][0] == "A2"
    finally:
        menu.deleteLater()


def test_left_menu_sync_moves_bottom_buttons(qapp):
    from sllkgui.guicore.window.left_menu.menu import CLeftMenu

    def item(btn_id: str, *, top: bool) -> dict:
        return {
            "btn_icon": "icon_star_fill",
            "btn_id": btn_id,
            "btn_text": btn_id,
            "btn_tooltip": btn_id,
            "btn_text_fallback": btn_id,
            "show_top": top,
            "is_active": False,
        }

    menu = CLeftMenu(None, None)
    try:
        menu.sync_menus([item("btn_top", top=True), item("btn_bottom", top=True)])
        assert menu._bottom_button_ids == set()
        menu.sync_menus([item("btn_top", top=True), item("btn_bottom", top=False)])
        assert menu._bottom_button_ids == {"btn_bottom"}
        assert menu.div_bottom.isVisible() or menu.div_bottom.isVisibleTo(menu)
    finally:
        menu.deleteLater()
