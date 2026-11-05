"""Fluent 设计令牌契约：几何、语义色与四主题一致性。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor

from sllkgui.appcore import AppSettings, ColorPalette, get_app_context, get_design_tokens, get_theme_manager
from sllkgui.guicore.custom_ui.button.severity import (
    Severity,
    Variant,
    colors_for,
    disabled_colors,
    is_dark_theme,
)
from sllkgui.guicore.custom_ui.line_edit.input_style import SIZES


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    get_app_context()
    app = QApplication.instance() or QApplication([])
    yield app
    get_theme_manager().apply("default")


def test_fluent_geometry_tokens(qapp):
    tokens = get_design_tokens()
    assert tokens.radius.control == 4
    assert tokens.radius.window == 8
    assert tokens.radius.tooltip == 8
    assert tokens.size.control_height == 32
    assert tokens.spacing.padding_sm == 8

    assert AppSettings.button.radius == 4
    assert AppSettings.button.disabled_opacity == pytest.approx(0.38)
    assert [SIZES[size].height for size in ("sm", "md", "lg")] == [28, 32, 40]


def test_fluent_semantic_outlined_uses_theme_color(qapp):
    colors = colors_for(Severity.SUCCESS, Variant.OUTLINED)
    assert colors.text.name() == QColor(ColorPalette.custom_green).name()
    assert colors.border.alpha() == 200
    assert colors.hover_background.alpha() > 0
    assert colors.background.alpha() == 0


def test_fluent_disabled_uses_neutral_fill(qapp):
    colors = disabled_colors(Variant.SOLID)
    assert colors.background.alpha() == 255
    assert colors.text.name() == QColor(ColorPalette.custom_text_description).name()
    # 禁用态不再把语义色整体降透明度
    assert colors.background.name() != QColor(ColorPalette.custom_context_color).name()


def test_fluent_tokens_follow_all_four_themes(qapp):
    seen = set()
    for theme in ("default", "bright", "eye", "dracula"):
        get_theme_manager().apply(theme)
        dark = is_dark_theme()
        colors = colors_for(Severity.WARN, Variant.SOLID)
        assert colors.background.alpha() == 255
        assert colors.text.name() in {
            QColor("#0b0b0b").name(),
            QColor("#ffffff").name(),
        }
        tokens = get_design_tokens()
        assert tokens.radius.control == 4
        assert tokens.radius.window == 8
        assert dark == (QColor(ColorPalette.custom_bg_one).lightness() < 128)
        seen.add(colors.background.name())
    get_theme_manager().apply("default")
    assert len(seen) == 4
