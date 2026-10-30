from AppCore import Language
from AppCore import get_plugin_registry
from Guis.windows.main_window.registry import (
    get_default_page_object,
    get_page_routes,
)


def test_registry_button_ids_unique():
    routes = get_page_routes(Language)
    assert len(routes) == len(set(routes))


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
