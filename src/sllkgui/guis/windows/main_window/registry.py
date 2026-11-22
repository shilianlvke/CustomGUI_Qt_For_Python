"""基座菜单与页面路由聚合（Gallery 版）。

窗口骨架只认这几个函数；插件页面由 :class:`GalleryRegistry` 提供，插件管理
等基座原生页面由 :mod:`native_pages` 提供。插件菜单按钮 ID 与页面 objectName
都由路由 ``plugin_id/surface_id`` 派生，页面控件在首次导航时按需构建。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from sllkgui.appcore import Logger, record_event

from .native_pages import NATIVE_PAGES, native_menu_items, native_page_for, native_page_routes

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查，guis 不反向依赖 gallery
    from sllkgui.gallery.registry import GalleryRegistry

BUILTIN_TITLE_MENU_ITEMS = [
    {
        "btn_icon": "icon_search",
        "btn_id": "btn_search",
        "btn_text": "language.UI.ui_Search",
        "btn_tooltip": "language.UI.ui_Search",
        "is_active": False,
    },
    {
        "btn_icon": "icon_setting",
        "btn_id": "btn_settings",
        "btn_text": "language.UI.ui_Settings",
        "btn_tooltip": "language.UI.ui_Settings",
        "is_active": False,
    },
]


def get_registry(window=None) -> GalleryRegistry | None:
    """返回窗口持有的插件注册表。

    注册表由组合根（``gallery/window.py``）挂在 ``window.gallery_registry`` 上；
    这里**不再回落到进程级单例**，``guis`` 因此不需要 import ``gallery``。
    """
    return getattr(window, "gallery_registry", None) if window is not None else None


def load_registered_pages(window, *, eager: bool = False):
    """页面改为首次导航时构建；这里只记录一次统计。"""
    registry = get_registry(window)
    count = registry.surface_count() if registry else 0
    Logger.debug(f"Gallery Surface 就绪: {count} 个 (eager={eager})")
    record_event("pages.loaded", category="ui", payload={"count": count, "eager": eager})


def notify_page_failure(code: str, detail: str = "") -> None:
    """页面构建失败的统一提示（``guis`` 侧，不依赖 ``gallery``）。

    走 toast 总线：去重键按错误码归一，连续失败只保留最新一条，避免启动期
    多个坏插件把屏幕铺满。
    """
    from sllkgui.appcore.feedback import (
        DedupePolicy,
        ToastAnchor,
        ToastLevel,
        ToastRequest,
    )
    from sllkgui.guicore.feedback import toast_bus

    try:
        toast_bus().show(
            ToastAnchor.AUTO,
            ToastRequest(
                text=detail or code,
                title="页面加载失败",
                level=ToastLevel.ERROR,
                detail=detail,
                code=code,
                scope="base",
                channel="base.pages",
                dedupe_key=f"pages.failure.{code}",
                dedupe=DedupePolicy.RESTART,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 提示失败不得影响导航
        Logger.debug(f"页面失败提示未发出: {exc}")


def ensure_registered_page(
    window,
    page_object: str,
    *,
    on_error: Callable[[str, str], None] | None = None,
) -> bool:
    """按 ``page_<路由>`` 构建 Surface / 原生页面并加入页面栈（幂等）。

    ``on_error(code, detail)`` 在任一失败分支被调用一次：调用方据此给出可定位
    提示（原生页走 :func:`notify_page_failure`，Gallery 窗口走自己的文案）。
    不传时保持旧行为（只写日志），便于测试与无 UI 场景。
    """

    def _fail(code: str, detail: str = "") -> bool:
        if on_error is not None:
            try:
                on_error(code, detail)
            except Exception as exc:  # noqa: BLE001 - 回调失败不影响返回值
                Logger.debug(f"页面失败回调异常: {exc}")
        return False

    if not page_object:
        return _fail("PAGE_OBJECT_EMPTY")
    pages = getattr(getattr(window, "ui", None), "load_pages", None)
    if pages is None:
        return _fail("PAGE_STACK_MISSING", page_object)
    if pages.pages.findChild(QWidget, page_object) is not None:
        return True
    native = native_page_for(page_object)
    if native is not None:
        try:
            widget = native.factory(window)
        except Exception as exc:  # noqa: BLE001 - 单个原生页面失败不影响其它页面
            Logger.exception(f"原生页面构建失败 {page_object}: {exc}")
            return _fail("NATIVE_PAGE_BUILD_FAILED", f"{page_object}: {exc}")
        if not isinstance(widget, QWidget):
            Logger.error(f"原生页面工厂未返回 QWidget: {page_object} -> {type(widget).__name__}")
            return _fail("NATIVE_PAGE_INVALID", page_object)
        widget.setObjectName(page_object)
        pages.pages.addWidget(widget)
        record_event("native_page.opened", category="ui", payload={"page": page_object})
        return True
    registry = get_registry(window)
    surface = registry.route_for_page(page_object) if registry else None
    if surface is None:
        Logger.warning(f"未找到 Surface 路由: {page_object}")
        return _fail("SURFACE_ROUTE_MISSING", page_object)
    if surface.plugin.context is None:
        Logger.warning(f"插件上下文缺失，无法构建 Surface: {surface.route}")
        return _fail("SURFACE_CONTEXT_MISSING", surface.route)
    try:
        widget = surface.factory(surface.plugin.context)
    except Exception as exc:  # noqa: BLE001 - 单个 Surface 失败不影响其它页面
        Logger.exception(f"Surface 构建失败 {surface.route}: {exc}")
        surface.plugin.context.report_error("SURFACE_BUILD_FAILED", f"Surface 构建失败: {surface.route}", str(exc))
        return _fail("SURFACE_BUILD_FAILED", f"{surface.route}: {exc}")
    if not isinstance(widget, QWidget):
        Logger.error(f"Surface 工厂未返回 QWidget: {surface.route} -> {type(widget).__name__}")
        return _fail("SURFACE_INVALID", surface.route)
    widget.setObjectName(page_object)
    pages.pages.addWidget(widget)
    surface.plugin.context.event("surface.opened", {"surface": surface.surface_id})
    return True


def get_page_routes(language=None, window=None):
    from sllkgui.appcore import Language

    # 旧调用方传入的是 Language 单例而非语言代码（PageRouterController 等），
    # 统一归一成字符串，避免 display_title 里 dict.get 抛 unhashable。
    code = language if isinstance(language, str) and language else Language.current()
    registry = get_registry(window)
    routes = registry.page_routes(code) if registry is not None else {}
    routes.update(native_page_routes())
    return routes


def get_default_page_object(window=None):
    """默认页面：优先插件的 default Surface，没有插件时回到原生插件管理。"""
    registry = get_registry(window)
    surface = registry.get(registry.default_route()) if registry is not None else None
    if surface is not None:
        return surface.page_object
    return NATIVE_PAGES[0].page_object if NATIVE_PAGES else ""


def get_menu_items(target: str, window=None):
    if target == "TitleMenu":
        return [dict(item) for item in BUILTIN_TITLE_MENU_ITEMS]
    if target == "LeftMenu":
        registry = get_registry(window)
        items = registry.menu_items() if registry is not None else []
        return [*items, *native_menu_items()]
    return []


__all__ = [
    "BUILTIN_TITLE_MENU_ITEMS",
    "ensure_registered_page",
    "get_default_page_object",
    "get_menu_items",
    "get_page_routes",
    "get_registry",
    "load_registered_pages",
]
