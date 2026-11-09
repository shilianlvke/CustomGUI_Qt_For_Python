from sllkgui.appcore import Language, get_plugin_registry
from sllkgui.guis.windows.main_window.registry import (
    get_default_page_object,
    get_page_routes,
)


def test_registry_button_ids_unique():
    """页面路由的 button_id 必须与已注册页面一一对应（FIX-12）。"""
    # FIX-12: 旧断言 len(routes) == len(set(routes)) 恒真（dict 键天然唯一），
    # 改用真实 page_plugins 的 button_id 列表比对，并自检确实扫描到路由。
    routes = get_page_routes(Language)
    button_ids = [plugin.button_id for plugin in get_plugin_registry().page_plugins()]
    assert len(routes) > 0, "should scan at least one page route"
    assert len(routes) == len(button_ids), "every registered page must map to exactly one route"


def test_page_routes_contains_core_entries():
    routes = get_page_routes(Language)

    # 基座目前只装配按钮预览应用
    assert "btn_button_preview" in routes


def test_default_page_exists_in_routes():
    routes = get_page_routes(Language)
    default_page = get_default_page_object()

    page_names = {page for page, _ in routes.values()}
    assert default_page in page_names


def test_default_page_is_button_preview():
    assert get_default_page_object() == "buttonPreviewPage"


def test_app_pages_registered_from_apps_directory():
    registry = get_plugin_registry()
    pages = registry.page_plugins()

    assert any(plugin.plugin_id == "app.page.button_preview" for plugin in pages)
