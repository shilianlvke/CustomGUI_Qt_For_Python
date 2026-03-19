import pytest

from AppCore.SYS.module.settings_module import (
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)


def _base_settings():
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


def _base_theme():
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


def _base_language():
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


def test_settings_validation_passes_for_valid_data():
    validate_settings_data(_base_settings())


def test_settings_validation_fails_when_required_field_missing():
    payload = _base_settings()
    payload.pop("time_animation")

    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_settings_data(payload)


def test_theme_validation_passes_for_valid_data():
    validate_theme_data(_base_theme(), "default")


def test_theme_validation_passes_when_optional_keys_missing():
    payload = _base_theme()
    payload.pop("custom_bg_active_one")
    payload.pop("custom_bg_active_two")
    payload.pop("custom_bg_active_three")
    payload.pop("custom_transparent")

    validate_theme_data(payload, "bright")


def test_theme_validation_fails_when_color_key_missing():
    payload = _base_theme()
    payload.pop("custom_text_active")

    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_theme_data(payload, "default")


def test_language_validation_passes_for_valid_data():
    validate_language_data(_base_language(), "en_us")


def test_language_validation_fails_when_required_group_missing():
    payload = _base_language()
    payload.pop("UI")

    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_language_data(payload, "en_us")