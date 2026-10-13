"""基座内置页面注册：欢迎页（组件展示）与底部信息按钮。

业务页面已迁移至 ``Apps/`` 目录，由 ``Guis.app_loader`` 发现并注册。
本模块只保留基座自带的欢迎界面与菜单聚合函数。
"""

from .normal_widget_show import NormalWidgetShowPage
from AppCore import MenuPlugin, PagePlugin, Logger, get_plugin_registry, record_event
from Guis.app_loader import load_apps

BUILTIN_MENU_PLUGINS = [
    MenuPlugin(
        plugin_id="builtin.menu.left.widget_show",
        target="LeftMenu",
        item={
            "btn_icon": "icon_home",
            "btn_id": "btn_widget_show",
            "btn_text": "language.PAGE.widget_show.title",
            "btn_tooltip": "language.PAGE.widget_show.title",
            "show_top": True,
            "is_active": True,
        },
    ),
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

BUILTIN_PAGE_PLUGINS = [
    PagePlugin(
        plugin_id="builtin.page.widget_show",
        button_id="btn_widget_show",
        page_object="normalWidgetShowPage",
        title_getter=lambda language: language.PAGE.widget_show.title,
        loader=NormalWidgetShowPage.load_page,
        default=True,
    ),
]


def _default_title_by_button(button_id):
    defaults = {
        "btn_widget_show": "Widget Show",
    }
    return defaults.get(button_id, "CustomUI")


def register_builtin_pages():
    registry = get_plugin_registry()
    for plugin in BUILTIN_PAGE_PLUGINS:
        if not registry.has_page(plugin.plugin_id):
            registry.register_page(plugin)


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


def load_registered_pages(window):
    load_apps()
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    registry.load_page_plugins(window)
    page_count = len(registry.page_plugins())
    Logger.debug(f"页面插件加载完成: {page_count} 个页面")
    record_event("pages.loaded", category="ui", payload={"count": page_count})


def get_page_routes(language):
    load_apps()
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    return registry.build_page_routes(language, _default_title_by_button)


def get_default_page_object():
    load_apps()
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    return registry.get_default_page_object()


def get_menu_items(target: str):
    load_apps()
    register_builtin_menus()
    registry = get_plugin_registry()
    return registry.apply_menu_plugins([], target)


register_builtin_menus()
register_builtin_pages()
PAGE_REGISTRY = _as_legacy_registry()


__all__ = [
    "NormalWidgetShowPage",
    "PAGE_REGISTRY",
    "load_registered_pages",
    "get_page_routes",
    "get_default_page_object",
    "get_menu_items",
]
