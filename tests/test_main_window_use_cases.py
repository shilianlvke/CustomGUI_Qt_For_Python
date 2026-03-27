from AppCore import MainWindowButtonUseCase


def test_use_case_identifies_page_route_first():
    """测试用例：test_use_case_identifies_page_route_first。

    职责:
    - 验证目标行为符合预期。
    """
    route = ("home_page", "Home")

    decision = MainWindowButtonUseCase.decide("btn_home", route=route)

    assert decision.kind == "page_route"
    assert decision.payload == route


def test_use_case_maps_action_buttons():
    "测试用例：test_use_case_maps_action_buttons。"
    decision = MainWindowButtonUseCase.decide("btn_close_left_column", route=None)

    assert decision.kind == "action"
    assert decision.payload == "btn_more"


def test_use_case_falls_back_to_plugin_command():
    "测试用例：test_use_case_falls_back_to_plugin_command。"
    decision = MainWindowButtonUseCase.decide("cmd_custom", route=None)

    assert decision.kind == "plugin_command"
    assert decision.payload == "cmd_custom"


def test_use_case_resets_left_tab_except_settings():
    "测试用例：test_use_case_resets_left_tab_except_settings。"
    assert MainWindowButtonUseCase.should_reset_left_tab("btn_home") is True
    assert MainWindowButtonUseCase.should_reset_left_tab("btn_settings") is False

