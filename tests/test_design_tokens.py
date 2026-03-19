from AppCore import AppSettings, ColorPalette, get_design_tokens


def test_design_tokens_reflect_current_settings_and_palette():
    tokens = get_design_tokens()

    assert tokens.typography.family == AppSettings.family
    assert tokens.typography.size_text == AppSettings.text_size
    assert tokens.radius.window == AppSettings.window_border_radius
    assert tokens.border.width == AppSettings.window_border_size
    assert tokens.colors.surface_app == ColorPalette.custom_bg_one
    assert tokens.colors.text_primary == ColorPalette.custom_text_foreground


def test_design_tokens_update_after_palette_change():
    old_value = ColorPalette.custom_bg_one
    try:
        ColorPalette.custom_bg_one = "#123456"
        tokens = get_design_tokens()
        assert tokens.colors.surface_app == "#123456"
    finally:
        ColorPalette.custom_bg_one = old_value
