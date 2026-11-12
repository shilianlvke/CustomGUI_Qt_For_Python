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


def _window(tmp_path, mode: str):
    from sllkgui.window import load_gallery, load_run

    if mode == "gallery":
        return load_gallery(data_dir=tmp_path / "gallery-data")
    return load_run(data_dir=tmp_path / "run-data")


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


def test_showcase_loads_ten_surfaces(tmp_path, prepared):
    window = _window(tmp_path, "gallery")
    try:
        routes = list(window.gallery_registry.routes())
        assert len(routes) == 10
        for route in routes:
            assert window.open_route(route), route
    finally:
        _close(window)


def test_core_store_loads_single_surface(tmp_path, prepared):
    window = _window(tmp_path, "run")
    try:
        routes = list(window.gallery_registry.routes())
        assert routes == ["com.sllkgui.core.store/store"]
        assert window.open_route(routes[0])
    finally:
        _close(window)


PAGES = {
    "buttons": ("buttons", "ButtonPreviewPage"),
    "tables": ("tables", "TablePreviewPage"),
    "data": ("data", "DataPreviewPage"),
    "feedback": ("feedback", "FeedbackPreviewPage"),
    "inputs": ("inputs", "InputPreviewPage"),
    "media": ("media", "MediaPreviewPage"),
    "menus": ("menus", "MenuPreviewPage"),
    "overlays": ("overlays", "OverlayPreviewPage"),
    "panels": ("panels", "PanelPreviewPage"),
    "shell": ("shell", "ShellPreviewPage"),
}


def test_showcase_pages_direct_build(tmp_path, prepared):
    """直接从真实包路径构建 10 个预览页（覆盖 page.py 的 sections 代码）。"""
    import importlib

    window = _window(tmp_path, "gallery")
    try:
        for module_name, class_name in PAGES.values():
            module = importlib.import_module(
                f"sllkgui.showcase.core_preview.surfaces.{module_name}.page"
            )
            page_class = getattr(module, class_name)
            widget = page_class.build(window)
            assert widget is not None
    finally:
        _close(window)


def test_window_navigation_reload_and_surface_helper(tmp_path, prepared):
    from sllkgui.gallery.window import surface_of

    window = _window(tmp_path, "gallery")
    try:
        assert window.open_route("missing/route") is False
        assert window.open_surface("com.sllkgui.showcase.core_preview", "tables") is True
        assert window.current_route().endswith("/tables")
        assert surface_of(window) is not None
        window.btn_released()
        window.btn_clicked()
        window.reload_plugins()
        assert window.gallery_registry.surface_count() == 10
    finally:
        _close(window)
