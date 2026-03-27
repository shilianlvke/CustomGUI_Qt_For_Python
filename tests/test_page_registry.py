"""模块说明。"""

import pytest

from AppCore import Language, get_plugin_registry
from GUI.windows.main_window.user_define_pages import (
    PAGE_REGISTRY,
    get_default_page_object,
    get_page_routes,
)


def test_registry_button_ids_unique() -> None:
    """测试用例：test_registry_button_ids_unique。

    职责:
    - 验证目标行为符合预期。
    """
    ids = [item["button_id"] for item in PAGE_REGISTRY]
    if len(ids) != len(set(ids)):
        pytest.fail("Assertion failed")


def test_page_routes_contains_core_entries() -> None:
    """测试用例：test_page_routes_contains_core_entries。"""
    routes = get_page_routes(Language)

    if "btn_home" not in routes:
        pytest.fail("Assertion failed")
    if "btn_test_case_lib" not in routes:
        pytest.fail("Assertion failed")
    if "btn_test_plan" not in routes:
        pytest.fail("Assertion failed")


def test_default_page_exists_in_routes() -> None:
    """测试用例：test_default_page_exists_in_routes。"""
    routes = get_page_routes(Language)
    default_page = get_default_page_object()

    page_names = {page for page, _ in routes.values()}
    if default_page not in page_names:
        pytest.fail("Assertion failed")


def test_builtin_page_plugins_registered() -> None:
    """测试用例：test_builtin_page_plugins_registered。"""
    registry = get_plugin_registry()
    pages = registry.page_plugins()

    if not (any(plugin.plugin_id == "builtin.page.home" for plugin in pages)):
        pytest.fail("Assertion failed")
