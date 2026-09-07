"""配置校验测试。"""

import pytest

from AppCore.system.module.settings_module import validate_language_data
from AppCore.system.module.token_models import ThemeColors, WindowSettings


def _base_settings() -> dict[str, object]:
    """返回一份合法的窗口设置样例。"""
    return {
        "startup_size": [960, 540],
        "minimum_size": [960, 540],
        "icon_size": 32,
        "custom_title_bar": True,
        "hide_grips": True,
        "window_margin": 2,
        "window_space": 2,
        "window_border_size": 2,
        "window_border_radius": 10,
        "window_shadow": True,
        "lef_menu_size": {"minimum": 50, "maximum": 200},
        "left_menu_content_margins": 2,
        "left_column_size": {"minimum": 0, "maximum": 240},
        "right_column_size": {"minimum": 0, "maximum": 240},
        "right_menu_content_margins": 3,
        "right_title_bar_height": 40,
        "right_content_space": 6,
        "right_credits_height": 40,
        "custom_padding": 10,
        "custom_border": 3,
        "tooltip_border_radius": 17,
        "tooltip_font": 300,
        "time_animation": 500,
        "family": "微软雅黑",
        "title_size": 18,
        "subtitle_size": 15,
        "text_size": 12,
    }


def _base_theme() -> dict[str, str]:
    """返回一份合法的主题颜色样例。"""
    return {
        "custom_dark_one": "#1a1d22",
        "custom_dark_two": "#1d2128",
        "custom_dark_three": "#20242c",
        "custom_dark_four": "#262b35",
        "custom_bg_one": "#2b303b",
        "custom_bg_two": "#333a47",
        "custom_bg_three": "#3b4353",
        "custom_bg_active_one": "#57965c",
        "custom_bg_active_two": "#ffcf49",
        "custom_bg_active_three": "#c94f4f",
        "custom_icon_color": "#b8c2d5",
        "custom_icon_hover": "#d0d6e2",
        "custom_icon_pressed": "#608edb",
        "custom_icon_active": "#e0e4eb",
        "custom_context_color": "#608edb",
        "custom_context_hover": "#76a5ed",
        "custom_context_pressed": "#4a78c5",
        "custom_text_title": "#d0d6e2",
        "custom_text_foreground": "#9ba5b8",
        "custom_text_description": "#6d788b",
        "custom_text_active": "#d0d6e2",
        "custom_white": "#eff2f7",
        "custom_pink": "#ff2a9b",
        "custom_green": "#62a167",
        "custom_red": "#d36565",
        "custom_yellow": "#ffd76a",
        "custom_transparent": "transparent",
    }


def _base_language() -> dict[str, object]:
    """返回一份合法的语言包样例。"""
    return {
        "custom_ui": {
            "sys_name": "CustomGUI",
            "sys_version": "1.0.0",
            "sys_copyright": "MIT",
            "sys_github": "https://example.com",
        },
        "PAGE": {"widget_show": {"title": "Widget"}},
        "UI": {"ui_Settings": "Settings", "ui_Show": "Show", "ui_Hide": "Hide"},
    }


def test_settings_validation_passes_for_valid_data() -> None:
    """合法设置应通过校验。"""
    WindowSettings.model_validate(_base_settings())


def test_settings_validation_ignores_extra_fields() -> None:
    """合并配置中的额外字段应被忽略。"""
    payload = _base_settings()
    payload["language"] = "zh_cn"
    payload["logger_level"] = "DEBUG"

    model = WindowSettings.model_validate(payload)
    if hasattr(model, "language"):
        pytest.fail("Assertion failed")


def test_settings_validation_fails_when_required_field_missing() -> None:
    """缺少必填字段时应抛校验错误。"""
    payload = _base_settings()
    payload.pop("time_animation")

    with pytest.raises(ValueError, match="time_animation"):
        WindowSettings.model_validate(payload)


def test_theme_validation_passes_for_valid_data() -> None:
    """合法主题应通过校验。"""
    ThemeColors.model_validate(_base_theme())


def test_theme_validation_passes_when_optional_keys_missing() -> None:
    """可选颜色字段缺失时应回落到默认值。"""
    payload = _base_theme()
    payload.pop("custom_bg_active_one")
    payload.pop("custom_bg_active_two")
    payload.pop("custom_bg_active_three")
    payload.pop("custom_transparent")

    model = ThemeColors.model_validate(payload)
    if model.custom_bg_active_one != "#57965c":
        pytest.fail("Assertion failed")
    if model.custom_transparent != "transparent":
        pytest.fail("Assertion failed")


def test_theme_validation_fails_when_color_key_missing() -> None:
    """缺少必填颜色字段时应抛校验错误。"""
    payload = _base_theme()
    payload.pop("custom_text_active")

    with pytest.raises(ValueError, match="custom_text_active"):
        ThemeColors.model_validate(payload)


def test_language_validation_passes_for_valid_data() -> None:
    """合法语言包应通过校验。"""
    validate_language_data(_base_language(), "en_us")


def test_language_validation_fails_when_required_group_missing() -> None:
    """缺少必填分组时应抛校验错误。"""
    payload = _base_language()
    payload.pop("UI")

    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_language_data(payload, "en_us")
