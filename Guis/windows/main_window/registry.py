"""基座菜单与页面路由聚合。

基座本身不包含任何页面：全部页面由 ``Apps/`` 目录的应用模组提供
（由 ``Guis.app_loader`` 发现注册）。本模块只负责：

- 基座内置菜单（底部「信息」按钮，属窗口控制入口而非页面）；
- 菜单项/页面路由/默认页的聚合查询。
"""

from PySide6.QtWidgets import QWidget

from AppCore import MenuPlugin, Logger, get_plugin_registry, record_event
from Guis.app_loader import load_apps

# 基座内置菜单：仅窗口控制入口（左列开关），不含页面
BUILTIN_MENU_PLUGINS = [
    MenuPlugin(
        plugin_id="builtin.menu.left.info",
        target="LeftMenu",
        item={
            "btn_icon": "icon_setting",
            "btn_id": "btn_info",
            "btn_text": "language.UI.ui_SoftwareInfo",
            "btn_tooltip": "language.UI.ui_SoftwareInfo",
            "show_top": False,
            "is_active": False,
        },
    ),
]


def _default_title_by_button(button_id):
    return "CustomUI"


def register_builtin_menus():
    registry = get_plugin_registry()
    for plugin in BUILTIN_MENU_PLUGINS:
        if plugin.plugin_id not in registry._menus:
            registry.register_menu(plugin)


def _as_legacy_registry():
    registry = get_plugin_registry()
    result = []
    for plugin in registry.page_plugins():
        result.append(
            {
                "button_id": plugin.button_id,
                "page_object": plugin.page_object,
                "title_getter": plugin.title_getter,
                "loader": plugin.loader,
                "default": plugin.default,
            }
        )
    return result


def load_registered_pages(window, *, eager: bool = False):
    """Load the default page (or every page when ``eager=True``).

    Non-default pages are instantiated lazily on first navigation, so a
    language change only rebuilds the page the user is looking at.
    """
    load_apps()
    register_builtin_menus()
    registry = get_plugin_registry()
    registry.load_page_plugins(window, eager=eager)
    page_count = len(registry.page_plugins())
    Logger.debug(f"页面插件加载完成: {page_count} 个页面 (eager={eager})")
    record_event("pages.loaded", category="ui", payload={"count": page_count, "eager": eager})


def ensure_registered_page(window, page_object: str) -> bool:
    """Instantiate a registered page if it is not in the stack yet."""
    if not page_object:
        return False
    pages = getattr(getattr(window, "ui", None), "load_pages", None)
    if pages is None:
        return False
    if pages.pages.findChild(QWidget, page_object) is not None:
        return True
    load_apps()
    registry = get_plugin_registry()
    plugin = registry.load_page_plugin(window, page_object)
    return plugin is not None and pages.pages.findChild(QWidget, page_object) is not None


def get_page_routes(language):
    load_apps()
    register_builtin_menus()
    registry = get_plugin_registry()
    return registry.build_page_routes(language, _default_title_by_button)


def get_default_page_object():
    load_apps()
    register_builtin_menus()
    registry = get_plugin_registry()
    return registry.get_default_page_object()


def get_menu_items(target: str):
    load_apps()
    register_builtin_menus()
    registry = get_plugin_registry()
    return registry.apply_menu_plugins([], target)


register_builtin_menus()
PAGE_REGISTRY = _as_legacy_registry()


__all__ = [
    "PAGE_REGISTRY",
    "load_registered_pages",
    "ensure_registered_page",
    "get_page_routes",
    "get_default_page_object",
    "get_menu_items",
]
