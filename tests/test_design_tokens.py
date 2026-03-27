"""模块说明。"""

import pytest

from AppCore import AppSettings, ColorPalette, get_design_tokens


def test_design_tokens_reflect_current_settings_and_palette() -> None:
    """测试用例：test_design_tokens_reflect_current_settings_and_palette。

    职责:
    - 验证目标行为符合预期。
    """
    tokens = get_design_tokens()

    if tokens.typography.family != AppSettings.family:
        pytest.fail("Assertion failed")
    if tokens.typography.size_text != AppSettings.text_size:
        pytest.fail("Assertion failed")
    if tokens.radius.window != AppSettings.window_border_radius:
        pytest.fail("Assertion failed")
    if tokens.border.width != AppSettings.window_border_size:
        pytest.fail("Assertion failed")
    if tokens.colors.surface_app != ColorPalette.custom_bg_one:
        pytest.fail("Assertion failed")
    if tokens.colors.text_primary != ColorPalette.custom_text_foreground:
        pytest.fail("Assertion failed")


def test_design_tokens_update_after_palette_change() -> None:
    """测试用例：test_design_tokens_update_after_palette_change。"""
    old_value = ColorPalette.custom_bg_one
    try:
        ColorPalette.custom_bg_one = "#123456"
        tokens = get_design_tokens()
        if tokens.colors.surface_app != "#123456":
            pytest.fail("Assertion failed")
    finally:
        ColorPalette.custom_bg_one = old_value
