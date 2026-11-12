"""基座菜单与页面路由聚合（Gallery 版）。

窗口骨架只认这几个函数；插件来源由 :class:`GalleryRegistry` 提供。菜单按钮
ID 与页面 objectName 都由路由 ``plugin_id/surface_id`` 派生，页面控件在首次
导航时按需构建。
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from sllkgui.appcore import Logger, record_event
from sllkgui.gallery.registry import GalleryRegistry, current_registry

#: 基座内置菜单：仅窗口控制入口（左列开关），不含页面
BUILTIN_LEFT_MENU_ITEMS = [
    {
        "btn_icon": "icon_setting",
        "btn_id": "btn_info",
        "btn_text": "language.UI.ui_SoftwareInfo",
        "btn_tooltip": "language.UI.ui_SoftwareInfo",
        "show_top": False,
        "is_active": False,
    },
]
BUILTIN_TITLE_MENU_ITEMS = [
    {
        "btn_icon": "icon_search",
        "btn_id": "btn_search",
        "btn_text": "language.UI.ui_Search",
        "btn_tooltip": "language.UI.ui_Search",
        "is_active": False,
    },
    {
        "btn_icon": "icon_palette",
        "btn_id": "btn_themes",
        "btn_text": "language.UI.ui_Appearance",
        "btn_tooltip": "language.UI.ui_Appearance",
        "is_active": False,
    },
]


def get_registry(window=None) -> GalleryRegistry | None:
    registry = getattr(window, "gallery_registry", None) if window is not None else None
    return registry or current_registry()


def register_builtin_menus() -> None:
    """保留旧入口：内置菜单现在由 :func:`get_menu_items` 直接拼装。"""


def load_registered_pages(window, *, eager: bool = False):
    """页面改为首次导航时构建；这里只记录一次统计。"""
    registry = get_registry(window)
    count = registry.surface_count() if registry else 0
    Logger.debug(f"Gallery Surface 就绪: {count} 个 (eager={eager})")
    record_event("pages.loaded", category="ui", payload={"count": count, "eager": eager})


def ensure_registered_page(window, page_object: str) -> bool:
    """按 ``page_<路由>`` 构建 Surface 并加入页面栈（幂等）。"""
    if not page_object:
        return False
    pages = getattr(getattr(window, "ui", None), "load_pages", None)
    if pages is None:
        return False
    if pages.pages.findChild(QWidget, page_object) is not None:
        return True
    registry = get_registry(window)
    surface = registry.route_for_page(page_object) if registry else None
    if surface is None:
        Logger.warning(f"未找到 Surface 路由: {page_object}")
        return False
    if surface.plugin.context is None:
        Logger.warning(f"插件上下文缺失，无法构建 Surface: {surface.route}")
        return False
    try:
        widget = surface.factory(surface.plugin.context)
    except Exception as exc:  # noqa: BLE001 - 单个 Surface 失败不影响其它页面
        Logger.exception(f"Surface 构建失败 {surface.route}: {exc}")
        surface.plugin.context.report_error("SURFACE_BUILD_FAILED", f"Surface 构建失败: {surface.route}", str(exc))
        return False
    if not isinstance(widget, QWidget):
        Logger.error(f"Surface 工厂未返回 QWidget: {surface.route} -> {type(widget).__name__}")
        return False
    widget.setObjectName(page_object)
    pages.pages.addWidget(widget)
    surface.plugin.context.event("surface.opened", {"surface": surface.surface_id})
    return True


def get_page_routes(language=None):
    registry = get_registry()
    if registry is None:
        return {}
    from sllkgui.appcore import Language

    # 旧调用方传入的是 Language 单例而非语言代码（PageRouterController 等），
    # 统一归一成字符串，避免 display_title 里 dict.get 抛 unhashable。
    code = language if isinstance(language, str) and language else Language.current()
    return registry.page_routes(code)


def get_default_page_object():
    registry = get_registry()
    if registry is None:
        return ""
    route = registry.default_route()
    surface = registry.get(route)
    return surface.page_object if surface is not None else ""


def get_menu_items(target: str):
    if target == "TitleMenu":
        return [dict(item) for item in BUILTIN_TITLE_MENU_ITEMS]
    if target == "LeftMenu":
        registry = get_registry()
        items = registry.menu_items() if registry is not None else []
        return [*items, *[dict(item) for item in BUILTIN_LEFT_MENU_ITEMS]]
    return []


#: 兼容旧代码的导入名；不再包含任何 App 页面。
PAGE_REGISTRY: list = []


__all__ = [
    "BUILTIN_LEFT_MENU_ITEMS",
    "BUILTIN_TITLE_MENU_ITEMS",
    "PAGE_REGISTRY",
    "ensure_registered_page",
    "get_default_page_object",
    "get_menu_items",
    "get_page_routes",
    "get_registry",
    "load_registered_pages",
    "register_builtin_menus",
]
