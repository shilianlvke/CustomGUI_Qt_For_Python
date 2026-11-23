"""Surface 导航生命周期钩子：enter/leave 导航级成对触发与去重。"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def prepared(qapp):
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


def _window(tmp_path):
    from sllkgui.window import load_gallery

    return load_gallery(data_dir=tmp_path / "gallery-data")


def _close(window) -> None:
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    window.runtime.shutdown()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    gc.collect()


def _spy_hooks(monkeypatch):
    """在插件类的钩子方法上挂记录，返回调用序列。

    需在创建窗口前调用，才能捕获 __init__ 里默认路由的首次 enter。
    """
    from sllkgui.plugin import Plugin

    calls: list[tuple[str, str]] = []

    def enter(self, surface_id: str):
        calls.append(("enter", surface_id))

    def leave(self, surface_id: str):
        calls.append(("leave", surface_id))

    monkeypatch.setattr(Plugin, "on_surface_enter", enter)
    monkeypatch.setattr(Plugin, "on_surface_leave", leave)
    return calls


def test_enter_leave_paired_on_switch(tmp_path, prepared, monkeypatch):
    calls = _spy_hooks(monkeypatch)
    window = _window(tmp_path)
    try:
        # __init__ 打开默认路由，已捕获其 enter
        routes = list(window.gallery_registry.routes())
        first, second = routes[0], routes[1]
        window.open_route(first)
        window.open_route(second)
        # 切页顺序：先 leave 旧 Surface，再 enter 新 Surface
        leave_old = ("leave", first.split("/")[-1])
        enter_new = ("enter", second.split("/")[-1])
        assert leave_old in calls
        assert enter_new in calls
        assert calls.index(leave_old) < calls.index(enter_new)
    finally:
        _close(window)


def test_same_route_repeat_does_not_retrigger(tmp_path, prepared, monkeypatch):
    calls = _spy_hooks(monkeypatch)
    window = _window(tmp_path)
    try:
        route = window.current_route()
        baseline = list(calls)
        window.open_route(route)
        assert calls == baseline  # 同页重复不触发
    finally:
        _close(window)


def test_native_page_switch_triggers_leave(tmp_path, prepared, monkeypatch):
    calls = _spy_hooks(monkeypatch)
    window = _window(tmp_path)
    try:
        route = window.current_route()
        surface_id = route.split("/")[-1]
        window._open_default_native_page()
        assert ("leave", surface_id) in calls
    finally:
        _close(window)


def test_clear_pages_triggers_leave(tmp_path, prepared, monkeypatch):
    calls = _spy_hooks(monkeypatch)
    window = _window(tmp_path)
    try:
        surface_id = window.current_route().split("/")[-1]
        window._clear_pages()
        assert ("leave", surface_id) in calls
    finally:
        _close(window)


def test_hook_exception_is_isolated(tmp_path, prepared, monkeypatch):
    from sllkgui.plugin import Plugin

    def boom(self, _surface_id):
        raise RuntimeError("hook boom")

    monkeypatch.setattr(Plugin, "on_surface_enter", boom)
    window = _window(tmp_path)
    try:
        route = next(r for r in window.gallery_registry.routes() if r != window.current_route())
        assert window.open_route(route) is True
    finally:
        _close(window)
