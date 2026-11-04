"""输入组件的尺寸规格与主题配色（对齐 Aura form.field）。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainterPath

from customgui.appcore import AppSettings, ColorPalette, get_design_tokens

from ...acrylic import acrylic_active, glass_tint
from ...styles import GLASS_CONTROL


@dataclass(frozen=True)
class InputSize:
    """一档尺寸的几何参数。"""

    height: int
    padding_x: int
    font_px: int
    icon_px: int


SIZES = {
    "sm": InputSize(height=32, padding_x=10, font_px=14, icon_px=14),
    "md": InputSize(height=40, padding_x=12, font_px=16, icon_px=16),
    "lg": InputSize(height=48, padding_x=14, font_px=18, icon_px=18),
}

#: Aura 表单圆角
RADIUS = 6
#: 图标与文本的间距
ICON_GAP = 6


def is_dark_theme() -> bool:
    """按内容区背景亮度判断主题深浅（四套主题通用）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def _mix(start: str, end: str, ratio: float) -> str:
    """把 ``start`` 按 ``ratio`` 混向 ``end``（用来派生 hover 描边）。"""
    begin, finish = QColor(start), QColor(end)
    return QColor(
        round(begin.red() + (finish.red() - begin.red()) * ratio),
        round(begin.green() + (finish.green() - begin.green()) * ratio),
        round(begin.blue() + (finish.blue() - begin.blue()) * ratio),
    ).name()


def colors() -> dict[str, str | QColor]:
    """当前主题下的输入组件配色。

    输入框没有 severity 维度，底色/描边/文字全部取设计令牌，与 ``styles.py`` 里
    ``#CInputText_LineEdit`` 的 QSS **同源**——自绘组件（下拉框、日期框、输入框组）
    才不会和 QLineEdit 的描边深浅不一。

    hover 描边取「常态描边 → 正文色」的 35% 混合：深色主题变亮、浅色主题变深，
    两个方向都是「更醒目」，不会像直接用 surface_interactive_hover 那样反向变淡。

    亚克力模式下底色/描边改成与 ``#CInputText_LineEdit`` 完全同一套半透明
    写法（``GLASS_CONTROL``）：自绘输入框（下拉框、数字框、日期框等）与
    原生 QLineEdit 并排时不会一实一透。
    """
    tokens = get_design_tokens().colors
    dark = is_dark_theme()
    if acrylic_active():
        background = glass_tint(tokens.surface_sidebar, GLASS_CONTROL)
        disabled_background = glass_tint(tokens.surface_app, 0.10)
        border = glass_tint(tokens.text_primary, 0.14)
        hover_border = glass_tint(tokens.text_primary, 0.28)
        addon_background = background
        control_border = glass_tint(tokens.text_primary, 0.24)
    else:
        background = tokens.surface_sidebar
        disabled_background = tokens.surface_app
        border = tokens.surface_interactive_pressed
        hover_border = _mix(border, tokens.text_primary, 0.35)
        addon_background = tokens.surface_sidebar
        control_border = border
    return {
        "background": background,
        "disabled_background": disabled_background,
        "border": border,
        "hover_border": hover_border,
        "focus_border": tokens.border_context,
        "invalid_border": "#f87171",
        "text": tokens.text_active,
        "placeholder": tokens.text_muted,
        # Aura 的 addon 底色与输入框同色，靠边框区分，不做深浅对比
        "addon_background": addon_background,
        "icon": tokens.text_primary if dark else tokens.text_muted,
        "control_border": control_border,
    }


def size_spec(size: str) -> InputSize:
    return SIZES.get(size, SIZES["md"])


def field_font(size: str = "md") -> QFont:
    """自绘字段统一字体（与 ``CButton`` 的取法一致）。"""
    font = QFont(AppSettings.family)
    font.setPixelSize(size_spec(size).font_px)
    return font


def corner_css(radius: int, corners: tuple[bool, bool, bool, bool] | None = None) -> str:
    """生成四角圆角声明；``corners`` 为 (左上, 右上, 右下, 左下)。"""
    if corners is None:
        return f"border-radius: {radius}px;"
    tl, tr, br, bl = (radius if flag else 0 for flag in corners)
    return (
        f"border-top-left-radius: {tl}px;"
        f" border-top-right-radius: {tr}px;"
        f" border-bottom-right-radius: {br}px;"
        f" border-bottom-left-radius: {bl}px;"
    )


def rounded_path(rect: QRectF, radius: float, corners: tuple[bool, bool, bool, bool] | None = None) -> QPainterPath:
    """自绘组件用的圆角路径（可只保留部分角）。"""
    flags = corners or (True, True, True, True)
    tl, tr, br, bl = (radius if flag else 0.0 for flag in flags)
    path = QPainterPath()
    path.moveTo(rect.left() + tl, rect.top())
    path.lineTo(rect.right() - tr, rect.top())
    if tr:
        path.arcTo(QRectF(rect.right() - 2 * tr, rect.top(), 2 * tr, 2 * tr), 90, -90)
    path.lineTo(rect.right(), rect.bottom() - br)
    if br:
        path.arcTo(QRectF(rect.right() - 2 * br, rect.bottom() - 2 * br, 2 * br, 2 * br), 0, -90)
    path.lineTo(rect.left() + bl, rect.bottom())
    if bl:
        path.arcTo(QRectF(rect.left(), rect.bottom() - 2 * bl, 2 * bl, 2 * bl), 270, -90)
    path.lineTo(rect.left(), rect.top() + tl)
    if tl:
        path.arcTo(QRectF(rect.left(), rect.top(), 2 * tl, 2 * tl), 180, -90)
    path.closeSubpath()
    return path


__all__ = [
    "InputSize",
    "SIZES",
    "RADIUS",
    "ICON_GAP",
    "colors",
    "corner_css",
    "field_font",
    "is_dark_theme",
    "rounded_path",
    "size_spec",
]
