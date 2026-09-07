"""模块说明。"""

import pytest

from AppCore import AppSettings, get_token_manager, initialize_tokens


def test_design_tokens_reflect_current_settings_and_palette() -> None:
    """测试用例：test_design_tokens_reflect_current_settings_and_palette。

    职责:
    - 验证设计令牌与当前设置、主题一致。
    """
    initialize_tokens()
    manager = get_token_manager()
    tokens = manager.tokens

    if tokens.typography.family != AppSettings.family:
        pytest.fail("Assertion failed")
    if tokens.typography.size_text != AppSettings.text_size:
        pytest.fail("Assertion failed")
    if tokens.radius.window != AppSettings.window_border_radius:
        pytest.fail("Assertion failed")
    if tokens.border.width != AppSettings.window_border_size:
        pytest.fail("Assertion failed")
    if tokens.colors.surface_app != manager.theme.custom_bg_one:
        pytest.fail("Assertion failed")
    if tokens.colors.text_primary != manager.theme.custom_text_foreground:
        pytest.fail("Assertion failed")


def test_design_tokens_update_after_theme_switch() -> None:
    """测试用例：test_design_tokens_update_after_theme_switch。

    职责:
    - 验证切换主题后设计令牌随之更新，切回后恢复。
    """
    initialize_tokens()
    manager = get_token_manager()
    default_surface = manager.tokens.colors.surface_app

    manager.switch_theme("bright")
    bright_surface = manager.tokens.colors.surface_app
    if bright_surface == default_surface:
        pytest.fail("切换主题后设计令牌应更新")
    if bright_surface != manager.theme.custom_bg_one:
        pytest.fail("Assertion failed")

    manager.switch_theme("default")
    if manager.tokens.colors.surface_app != default_surface:
        pytest.fail("切回默认主题后令牌应恢复")
