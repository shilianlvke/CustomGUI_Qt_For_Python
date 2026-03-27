# ruff: noqa: N999
"""Package initialization module."""

from AppCore import MenuPlugin, PagePlugin, get_plugin_registry

from .normal_widget_show import NormalWidgetShowPage
from .p2ptest_analysis_manage import P2PTestAnalysisPage
from .p2ptest_case_manage import P2PTestCaseLibPage
from .p2ptest_database_manage import P2PTestDataBasePage
from .p2ptest_home_manage import P2PTestHomePage
from .p2ptest_plan_manage import P2PTestPlanPage
from .p2ptest_report_manage import P2PTestReportPage
from .p2ptest_tester_manage import P2PTestTesterPage

BUILTIN_MENU_PLUGINS = [
    MenuPlugin(
        plugin_id="builtin.menu.left.widget_show",
        target="LeftMenu",
        item={
            "btn_icon": "icon_home",
            "btn_id": "btn_widget_show",
            "btn_text": "组件展示",
            "btn_tooltip": "组件展示",
            "show_top": True,
            "is_active": True,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.home",
        target="LeftMenu",
        item={
            "btn_icon": "icon_home",
            "btn_id": "btn_home",
            "btn_text": "CustomUI",
            "btn_tooltip": "CustomUI",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.case_lib",
        target="LeftMenu",
        item={
            "btn_icon": "icon_case_lib",
            "btn_id": "btn_test_case_lib",
            "btn_text": "测试用例库",
            "btn_tooltip": "测试用例库",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.plan",
        target="LeftMenu",
        item={
            "btn_icon": "icon_plan",
            "btn_id": "btn_test_plan",
            "btn_text": "测试计划",
            "btn_tooltip": "测试计划",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.report",
        target="LeftMenu",
        item={
            "btn_icon": "icon_report",
            "btn_id": "btn_test_result",
            "btn_text": "测试报告",
            "btn_tooltip": "测试报告",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.analysis",
        target="LeftMenu",
        item={
            "btn_icon": "icon_analysis",
            "btn_id": "btn_test_plan_show",
            "btn_text": "测试分析",
            "btn_tooltip": "测试分析",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.users",
        target="LeftMenu",
        item={
            "btn_icon": "icon_users",
            "btn_id": "btn_test_users",
            "btn_text": "用户管理",
            "btn_tooltip": "用户管理",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.database",
        target="LeftMenu",
        item={
            "btn_icon": "icon_database",
            "btn_id": "btn_test_database",
            "btn_text": "归档及配置",
            "btn_tooltip": "归档及配置",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.wiki",
        target="LeftMenu",
        item={
            "btn_icon": "icon_books",
            "btn_id": "btn_test_wiki",
            "btn_text": "测试 wiki",
            "btn_tooltip": "测试 wiki",
            "show_top": True,
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.left.info",
        target="LeftMenu",
        item={
            "btn_icon": "icon_setting",
            "btn_id": "btn_info",
            "btn_text": "信息",
            "btn_tooltip": "软件信息",
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
    PagePlugin(
        plugin_id="builtin.page.home",
        button_id="btn_home",
        page_object="p2pTestHomePage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestHomePage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.case_lib",
        button_id="btn_test_case_lib",
        page_object="p2pTestCaseLibPage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestCaseLibPage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.plan",
        button_id="btn_test_plan",
        page_object="p2pTestPlanPage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestPlanPage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.report",
        button_id="btn_test_result",
        page_object="p2pTestReportPage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestReportPage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.analysis",
        button_id="btn_test_plan_show",
        page_object="p2pTestAnalysisPage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestAnalysisPage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.tester",
        button_id="btn_test_users",
        page_object="p2pTestTesterPage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestTesterPage.load_page,
    ),
    PagePlugin(
        plugin_id="builtin.page.database",
        button_id="btn_test_database",
        page_object="p2pTestDataBasePage",
        title_getter=lambda language: language.custom_ui.sys_name,
        loader=P2PTestDataBasePage.load_page,
    ),
]


def _default_title_by_button(button_id: str) -> str:
    """按按钮 ID 提供默认标题。

    参数:
    - button_id: 按钮标识。

    返回:
    - str: 默认标题文本。
    """
    defaults = {
        "btn_widget_show": "Widget Show",
    }
    return defaults.get(button_id, "CustomUI")


def register_builtin_pages() -> None:
    """注册内置页面插件。

    返回:
    - None
    """
    registry = get_plugin_registry()
    for plugin in BUILTIN_PAGE_PLUGINS:
        if not registry.has_page(plugin.plugin_id):
            registry.register_page(plugin)


def register_builtin_menus() -> None:
    """注册内置菜单插件。

    返回:
    - None
    """
    registry = get_plugin_registry()
    for plugin in BUILTIN_MENU_PLUGINS:
        if not registry.has_menu(plugin.plugin_id):
            registry.register_menu(plugin)


def _as_legacy_registry() -> list[dict[str, object]]:
    """导出兼容历史结构的页面注册表。

    返回:
    - list[dict]: 兼容旧接口的页面信息列表。
    """
    registry = get_plugin_registry()
    return [
        {
            "button_id": plugin.button_id,
            "page_object": plugin.page_object,
            "title_getter": plugin.title_getter,
            "loader": plugin.loader,
            "default": plugin.default,
        }
        for plugin in registry.page_plugins()
    ]


def load_registered_pages(window: object) -> None:
    """加载并执行已注册页面插件。

    参数:
    - window: 主窗口对象。

    返回:
    - None
    """
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    registry.load_page_plugins(window)


def get_page_routes(
    language: object,
) -> dict[str, tuple[str, str]]:
    """获取页面路由映射。

    参数:
    - language: 当前语言对象。

    返回:
    - dict: ``button_id -> (page_object, title)`` 映射。
    """
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    return registry.build_page_routes(language, _default_title_by_button)


def get_default_page_object() -> str:
    """获取默认页面对象名。

    返回:
    - str: 默认页面对象名。
    """
    register_builtin_menus()
    register_builtin_pages()
    registry = get_plugin_registry()
    return registry.get_default_page_object()


def get_menu_items(target: str) -> list[dict[str, object]]:
    """获取指定菜单目标的菜单项。

    参数:
    - target: 菜单目标标识。

    返回:
    - list: 菜单项列表。
    """
    register_builtin_menus()
    registry = get_plugin_registry()
    return registry.apply_menu_plugins([], target)


register_builtin_menus()
register_builtin_pages()
PAGE_REGISTRY = _as_legacy_registry()


__all__ = [
    "PAGE_REGISTRY",
    "NormalWidgetShowPage",
    "P2PTestAnalysisPage",
    "P2PTestCaseLibPage",
    "P2PTestDataBasePage",
    "P2PTestHomePage",
    "P2PTestPlanPage",
    "P2PTestReportPage",
    "P2PTestTesterPage",
    "get_default_page_object",
    "get_menu_items",
    "get_page_routes",
    "load_registered_pages",
]

