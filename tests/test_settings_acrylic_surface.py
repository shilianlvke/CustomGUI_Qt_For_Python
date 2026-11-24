"""设置页亚克力：用户参数、迁移、材质开关与窗口底色。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage, QPainter

from sllkgui.appcore import (
    KEY_SETTINGS_ACRYLIC,
    SettingsRegistry,
    SettingsSession,
    SettingsStore,
    ensure_core_pages,
    user_settings,
)
from sllkgui.guicore.styles import window_surface_gradient
from sllkgui.guicore.window.settings_window import CSettingsWindow
from sllkgui.guicore.window.settings_window import window as settings_window_module


class _MemoryCore:
    def __init__(self, data: dict | None = None) -> None:
        self.data = dict(data or {})

    def load(self) -> dict:
        return dict(self.data)

    def save(self, updates) -> bool:
        self.data.update(dict(updates))
        return True

    def path(self) -> Path:
        return Path("user.yaml")


def _session(tmp_path: Path, data: dict | None = None) -> SettingsSession:
    registry = SettingsRegistry()
    ensure_core_pages(registry)
    store = SettingsStore(settings_dir=tmp_path, core=_MemoryCore(data))
    return SettingsSession(registry=registry, store=store)


def test_settings_acrylic_spec_and_schema_defaults(qapp, tmp_path):
    """新开关注册在 appearance 页，默认开启并随 v7 迁移写入。"""
    session = _session(tmp_path, {"schema_version": user_settings.SCHEMA_VERSION})
    page, spec = session.spec(KEY_SETTINGS_ACRYLIC)

    assert page.page_id == "appearance"
    assert spec.default is True
    assert spec.storage_key == "settings_acrylic"
    assert session.value(KEY_SETTINGS_ACRYLIC) is True

    migrated = user_settings._migrate_state({}, version=6, fill_defaults=True)
    assert migrated["settings_acrylic"] is True
    assert user_settings.SCHEMA_VERSION == 7


def test_settings_acrylic_disabled_keeps_existing_false(qapp, tmp_path):
    """迁移只补缺失字段，不覆盖用户已经关闭的开关。"""
    session = _session(tmp_path, {"schema_version": 6, "settings_acrylic": False})

    assert session.value(KEY_SETTINGS_ACRYLIC) is False
    assert user_settings.SCHEMA_VERSION == 7


def test_settings_window_uses_user_switch_for_acrylic(qapp, tmp_path, monkeypatch):
    """窗口按用户参数决定挂载/移除系统材质，并只影响自身。"""
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(settings_window_module, "acrylic_active", lambda: True)
    monkeypatch.setattr(
        settings_window_module,
        "apply_acrylic",
        lambda widget: calls.append(("apply", widget)),
    )
    monkeypatch.setattr(
        settings_window_module,
        "remove_acrylic",
        lambda widget: calls.append(("remove", widget)),
    )

    on_window = CSettingsWindow(session=_session(tmp_path, {"settings_acrylic": True}))
    on_window.show()
    qapp.processEvents()
    assert ("apply", on_window) in calls

    calls.clear()
    off_window = CSettingsWindow(session=_session(tmp_path, {"settings_acrylic": False}))
    off_window.show()
    qapp.processEvents()
    assert ("remove", off_window) in calls

    off_window.set_settings_acrylic(True)
    assert calls[-1] == ("apply", off_window)
    off_window.set_settings_acrylic(False)
    assert calls[-1] == ("remove", off_window)

    on_window.close()
    off_window.close()


def test_window_surface_gradient_alpha_tracks_glass_flag(qapp):
    """同一窗口底色：玻璃模式半透明，关闭时完全不透明。"""
    image = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(image.rect(), window_surface_gradient(image.rect(), glass=False))
    painter.end()
    assert image.pixelColor(32, 32).alpha() == 255

    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(image.rect(), window_surface_gradient(image.rect(), glass=True))
    painter.end()
    assert image.pixelColor(32, 32).alpha() < 255


def test_settings_acrylic_default_without_stored_value(qapp, tmp_path):
    """老用户没有该字段时仍按默认开启，不依赖手写迁移。"""
    session = _session(tmp_path, {"theme_name": "bright"})

    assert session.value(KEY_SETTINGS_ACRYLIC) is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
