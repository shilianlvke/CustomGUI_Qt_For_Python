"""Gallery 窗口：插件重载必须能原地停留在插件管理页。

这是「启停/更新后跳到别的页面」的直接回归：旧的 ``reload_plugins()`` 在重载后
只认插件路由，原生页不在路由里，于是回落到 ``default_route()``/原生首页，
用户就被弹离插件管理页。
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeWindow:
    """只保留 reload_plugins 依赖的窗口成员，避免构造完整主窗口。"""

    pass


def _registry(*, routes=None):
    """最小注册表桩：reload_plugins 只用到 get / menu_items / default_route。"""
    known = routes or {}

    class _Registry:
        def get(self, route):
            return known.get(route)

        def menu_items(self):
            return []

        def default_route(self):
            return ""

    return _Registry()


def _window_shell():
    """用最小桩件验证 reload_plugins 的页面选择逻辑。"""
    from sllkgui.gallery.window import GalleryWindow

    window = _FakeWindow()
    window._current_route = ""
    window.runtime = SimpleNamespace(
        registry=_registry(),
        default_route=lambda: "",
        reload=lambda: None,
    )
    window.gallery_registry = _registry()
    window.ui = SimpleNamespace(
        left_menu=SimpleNamespace(
            clear_menus=lambda: None,
            add_menus=lambda items: None,
        ),
        load_pages=SimpleNamespace(pages=SimpleNamespace(currentWidget=lambda: None)),
    )
    opened: list[str] = []
    window._clear_pages = lambda: None
    window._show_empty_state = lambda: opened.append("empty")
    window._open_default_native_page = lambda: False
    window.open_route = lambda route: bool(opened.append(route)) or True

    def _open_native(native):
        opened.append(native.page_object)
        return True

    window._open_native_page = _open_native
    window._opened = opened
    window._active_route = ""
    window._current_native = None
    # 绑定真实实现
    window.reload_plugins = GalleryWindow.reload_plugins.__get__(window)
    window.reload_plugins_in_place = GalleryWindow.reload_plugins_in_place.__get__(window)
    window._current_native_page = GalleryWindow._current_native_page.__get__(window)
    return window


def test_reload_with_native_page_stays_there():
    """传入原生页 page_object 时，重载后停在该页而不是默认路由。"""
    window = _window_shell()
    window.reload_plugins("page_native_plugin_store")
    assert window._opened == ["page_native_plugin_store"]


def test_reload_in_place_helper():
    window = _window_shell()
    window.reload_plugins_in_place("page_native_plugin_store")
    assert window._opened == ["page_native_plugin_store"]


def test_reload_without_hint_keeps_old_behaviour():
    """不传提示时保持原语义：沿用旧路由。"""
    window = _window_shell()
    window.runtime.registry = _registry(routes={"a/one": object()})
    window._current_route = "a/one"
    window.reload_plugins()
    assert window._opened == ["a/one"]


def test_reload_unknown_native_page_falls_back():
    """未知 page_object 不能被当成原生页，应回落到原逻辑而不是黑屏。"""
    window = _window_shell()
    window.reload_plugins("not_a_native_page")
    assert "not_a_native_page" not in window._opened


def test_reload_detects_current_native_page_without_hint():
    """调用方忘记传 page_object 时，按菜单当前停留的原生页原地重建。"""
    window = _window_shell()
    window.ui.left_menu.active_button_id = lambda: "btn_native_plugin_store"
    window._active_route = ""
    window.reload_plugins()
    assert window._opened == ["page_native_plugin_store"]


def test_reload_ignores_native_detection_on_plugin_surface():
    """当前在插件 Surface 上时必须沿用路由，不能被原生页抢走。"""
    window = _window_shell()
    window.ui.left_menu.active_button_id = lambda: "btn_native_plugin_store"
    window._active_route = "a/one"
    window.runtime.registry = _registry(routes={"a/one": object()})
    window._current_route = "a/one"
    window.reload_plugins()
    assert window._opened == ["a/one"]
