"""模块说明。"""

import pytest

from AppCore import MainWindowButtonUseCase


def test_use_case_identifies_page_route_first() -> None:
    """测试用例：test_use_case_identifies_page_route_first。

    职责:
    - 验证目标行为符合预期。
    """
    route = ("home_page", "Home")

    decision = MainWindowButtonUseCase.decide("btn_home", route=route)

    if decision.kind != "page_route":
        pytest.fail("Assertion failed")
    if decision.payload != route:
        pytest.fail("Assertion failed")


def test_use_case_maps_action_buttons() -> None:
    """测试用例：test_use_case_maps_action_buttons。"""
    decision = MainWindowButtonUseCase.decide("btn_close_left_column", route=None)

    if decision.kind != "action":
        pytest.fail("Assertion failed")
    if decision.payload != "btn_more":
        pytest.fail("Assertion failed")


def test_use_case_falls_back_to_plugin_command() -> None:
    """测试用例：test_use_case_falls_back_to_plugin_command。"""
    decision = MainWindowButtonUseCase.decide("cmd_custom", route=None)

    if decision.kind != "plugin_command":
        pytest.fail("Assertion failed")
    if decision.payload != "cmd_custom":
        pytest.fail("Assertion failed")


def test_use_case_resets_left_tab_except_settings() -> None:
    """测试用例：test_use_case_resets_left_tab_except_settings。"""
    if MainWindowButtonUseCase.should_reset_left_tab("btn_home") is not True:
        pytest.fail("Assertion failed")
    if MainWindowButtonUseCase.should_reset_left_tab("btn_settings") is not False:
        pytest.fail("Assertion failed")
