"""输入组件的尺寸规格与主题配色（对齐 Aura form.field）。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainterPath

from AppCore import AppSettings, ColorPalette


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


def colors() -> dict[str, str]:
    """当前主题下的输入组件配色。

    输入框没有 severity 维度，深色沿用基座暗色层，浅色对齐 Aura light。
    """
    if is_dark_theme():
        return {
            "background": ColorPalette.custom_dark_one,
            "disabled_background": ColorPalette.custom_dark_two,
            "border": ColorPalette.custom_dark_four,
            "hover_border": ColorPalette.custom_bg_two,
            "focus_border": ColorPalette.custom_context_color,
            "invalid_border": "#fca5a5",
            "text": ColorPalette.custom_text_title,
            "placeholder": ColorPalette.custom_text_description,
            "addon_background": ColorPalette.custom_dark_three,
            "icon": ColorPalette.custom_icon_color,
            "control_border": "#3f3f46",
        }
    return {
        "background": "#ffffff",
        "disabled_background": "#e2e8f0",
        "border": "#cbd5e1",
        "hover_border": "#94a3b8",
        "focus_border": ColorPalette.custom_context_color,
        "invalid_border": "#f87171",
        "text": "#334155",
        "placeholder": "#64748b",
        "addon_background": "#f8fafc",
        "icon": "#64748b",
        "control_border": "#94a3b8",
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
