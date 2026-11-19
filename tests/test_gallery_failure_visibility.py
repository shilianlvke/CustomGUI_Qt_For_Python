"""插件加载 / 页面构建失败必须对户可见（RV-09 回归）。

失败路径仍只写日志不足以让用户区分「没反应」和「卡住」；
这里锁定 GalleryWindow 通过 CToast 给出可定位的最小信息。
"""

from __future__ import annotations

import pytest


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


def _spy_toast(monkeypatch):
    from sllkgui.guicore import CToast

    calls: list[dict] = []

    def fake_show_message(cls, parent, text, title="", severity="info", life=None, offset_top=0):
        calls.append({"parent": parent, "text": text, "title": title, "severity": severity})

    monkeypatch.setattr(CToast, "show_message", classmethod(fake_show_message))
    return calls


def test_missing_route_shows_toast(tmp_path, prepared, monkeypatch):
    calls = _spy_toast(monkeypatch)
    window = _window(tmp_path)
    try:
        assert window.open_route("missing/route") is False
        assert calls, "路由不存在时必须有可见提示"
        assert "missing/route" in calls[-1]["text"]
        assert calls[-1]["severity"] == "error"
    finally:
        _close(window)


def test_surface_build_failure_shows_code_and_log_hint(tmp_path, prepared, monkeypatch):
    calls = _spy_toast(monkeypatch)
    window = _window(tmp_path)
    try:
        # __init__ 已构建默认路由；选一个尚未构建的 Surface 才能触发工厂失败分支
        route = next(r for r in window.gallery_registry.routes() if r != window.current_route())
        surface = window.gallery_registry.get(route)

        def boom(_ctx):
            raise RuntimeError("boom")

        monkeypatch.setattr(surface, "factory", boom)
        assert window.open_route(route) is False
        assert calls, "Surface 构建失败时必须有可见提示"
        text = calls[-1]["text"]
        assert surface.route in text
        assert "SURFACE_BUILD_FAILED" in text
        assert "详情见日志" in text
        assert window.runtime.last_error is not None
        assert window.runtime.last_error["code"] == "SURFACE_BUILD_FAILED"
    finally:
        _close(window)
