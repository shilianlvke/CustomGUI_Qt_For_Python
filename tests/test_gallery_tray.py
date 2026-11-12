"""基座托盘：动作注册、权限校验与关闭到托盘。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.gallery.api import Permission
from sllkgui.gallery.context import GalleryContextImpl
from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.manifest import PluginManifest
from sllkgui.gallery.store import GalleryStore
from sllkgui.gallery.tray import TrayHandle, TrayService


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def prepared(app):
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


def _manifest(tmp_path: Path, permissions: tuple[Permission, ...]) -> PluginManifest:
    return PluginManifest(
        schema=1,
        api=1,
        plugin_id="com.example.tray",
        name="Tray",
        version="1.0.0",
        entry="plugin.py",
        root=tmp_path,
        permissions=permissions,
    )


def _context(tmp_path: Path, permissions: tuple[Permission, ...]) -> GalleryContextImpl:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return GalleryContextImpl(_manifest(tmp_path, permissions), store, tray=TrayService())


def test_tray_actions_are_registered_per_plugin():
    service = TrayService()
    service.add_action("a:one", "One", lambda: None, order=10, plugin_id="a")
    service.add_action("b:two", "Two", lambda: None, order=20, plugin_id="b")
    assert service.action_count() == 2
    assert service.action_count("a") == 1
    service.remove_plugin("a")
    assert service.action_count("a") == 0
    assert service.action_count() == 1


def test_tray_handle_requires_permissions(tmp_path: Path):
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", ())
    with pytest.raises(GalleryError) as exc:
        handle.add_action("toggle", "Toggle", lambda: None)
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"

    without_notifications = TrayHandle(service, "com.example.tray", (Permission.TRAY,))
    with pytest.raises(GalleryError) as exc:
        without_notifications.show_message("t", "m")
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


def test_tray_handle_clear_removes_actions():
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", (Permission.TRAY,))
    handle.add_action("toggle", "Toggle", lambda: None)
    handle.add_action("save", "Save", lambda: None)
    assert service.action_count("com.example.tray") == 2
    handle.clear()
    assert service.action_count("com.example.tray") == 0


def test_context_tray_denied_without_permission(tmp_path: Path):
    ctx = _context(tmp_path, ())
    with pytest.raises(GalleryError) as exc:
        _ = ctx.tray
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


def test_context_tray_available_with_permission(tmp_path: Path):
    ctx = _context(tmp_path, (Permission.TRAY,))
    assert ctx.tray is not None
    assert ctx.tray.available() in (True, False)


def test_window_close_hides_to_tray_when_active(tmp_path: Path, prepared):
    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-data")
    window.runtime.tray.is_active = lambda: True  # type: ignore[method-assign]
    window.show()
    window.close()
    assert window.isVisible() is False
    assert window.runtime.records, "关闭到托盘时不应卸载插件"
    window._force_close = True
    window.close()
    assert window.runtime.records == []
