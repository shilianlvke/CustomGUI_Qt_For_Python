"""页面专用的绘制/排版工具：颜色、字体与几何。

只放"这一页需要、但还不足以进组件库"的工具；颜色取值仍来自
``guicore`` 的 ``panel_colors`` / ``card_surface_color``。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import ColorPalette, get_design_tokens
from sllkgui.guicore.fonts import MONO_FAMILIES as _MONO_FAMILIES
from sllkgui.guicore.styles import card_surface_color


def _toast_offset(window) -> int:
    """通知条避让标题栏：顶部偏移 = 标题栏高度 + 8。"""
    bar = getattr(getattr(window, "ui", None), "title_bar", None)
    return bar.height() + 8 if bar is not None else 56


# ----------------------------------------------------------------------
# 绘制工具
# ----------------------------------------------------------------------
def _tint(color: str | QColor, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(alpha)
    return value


def _font(base: QFont, size: int, weight: QFont.Weight = QFont.Weight.Normal, *, mono: bool = False) -> QFont:
    font = QFont(base)
    font.setPixelSize(size)
    font.setWeight(weight)
    if mono:
        font.setFamilies(_MONO_FAMILIES)
    return font


def _card_rect(widget: QWidget) -> QRectF:
    return QRectF(widget.rect()).adjusted(0.75, 0.75, -0.75, -0.75)


def _surface_color() -> QColor:
    """外层卡片底色：与 ``CCard`` 的 ``surface_card`` 一致（#44475a）。"""
    return QColor(card_surface_color())


def _line_color() -> QColor:
    """卡片描边：取交互按压层，保证在两种底色上都清晰可见（#595D75）。"""
    return QColor(get_design_tokens().colors.surface_interactive_pressed)


def _hover_color() -> QColor:
    return QColor(ColorPalette.custom_dark_four)


#: 与 py-rm page_kit 对齐的排版角色
_ROLE_SIZES = {"eyebrow": 8, "title": 18, "section": 12, "metric": 24, "body": 10, "muted": 9, "entry": 13, "value": 11}
