"""主题持久化经 SettingsSession 与单一键声明（RV-05 方案 C 回归）。"""

from __future__ import annotations

from types import SimpleNamespace

from sllkgui.appcore import KEY_THEME
from sllkgui.appcore.settings.base import STORAGE_THEME
from sllkgui.guis.windows.main_window import controller as controller_module
from sllkgui.guis.windows.main_window.controller import SettingsController


def test_storage_and_full_key_share_one_declaration():
    """键名只有一处声明：完整键与历史存储键来自同一个 base 模块。"""
    assert KEY_THEME == "core.appearance.theme"
    assert STORAGE_THEME == "theme_name"


def test_theme_change_persists_through_session_with_full_key(monkeypatch):
    calls: list[tuple[str, object]] = []
    saves: list[int] = []

    class _FakeSession:
        def set(self, key, value):
            calls.append((key, value))
            return True

        def save(self):
            saves.append(1)
            return True

    monkeypatch.setattr(controller_module, "ensure_core_pages", lambda: None)
    monkeypatch.setattr(controller_module, "SettingsSession", _FakeSession)

    class _Styles:
        def __init__(self):
            self.style = "demo-style"

    window = SimpleNamespace(ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: None)))
    manager = SimpleNamespace(current=lambda: "bright", subscribe=lambda cb: None, unsubscribe=lambda cb: None)
    controller = SettingsController(window=window, theme_manager=manager, style_factory=_Styles)

    controller._apply_styles()

    assert calls == [(KEY_THEME, "bright")]
    assert len(saves) == 1


def test_theme_preview_does_not_persist(monkeypatch):
    saves: list[int] = []

    class _FakeSession:
        def set(self, key, value):
            return True

        def save(self):
            saves.append(1)
            return True

    monkeypatch.setattr(controller_module, "SettingsSession", _FakeSession)

    class _Styles:
        def __init__(self):
            self.style = "demo-style"

    window = SimpleNamespace(ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: None)))
    manager = SimpleNamespace(current=lambda: "bright", subscribe=lambda cb: None, unsubscribe=lambda cb: None)
    controller = SettingsController(window=window, theme_manager=manager, style_factory=_Styles)
    controller._previewing_theme = True

    controller._apply_styles()

    assert saves == []


def test_session_save_reentry_is_blocked(monkeypatch):
    """save() 再次触发 _apply_styles 时不得递归写盘。"""
    saves: list[int] = []
    controller_holder: dict = {}

    class _FakeSession:
        def set(self, key, value):
            return True

        def save(self):
            saves.append(1)
            controller_holder["controller"]._apply_styles()
            return True

    monkeypatch.setattr(controller_module, "ensure_core_pages", lambda: None)
    monkeypatch.setattr(controller_module, "SettingsSession", _FakeSession)

    class _Styles:
        def __init__(self):
            self.style = "demo-style"

    window = SimpleNamespace(ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: None)))
    manager = SimpleNamespace(current=lambda: "bright", subscribe=lambda cb: None, unsubscribe=lambda cb: None)
    controller = SettingsController(window=window, theme_manager=manager, style_factory=_Styles)
    controller_holder["controller"] = controller

    controller._apply_styles()

    assert len(saves) == 1
