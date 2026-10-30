"""状态原子件的主题色（与基座调色板对齐，切换主题实时生效）。"""

from __future__ import annotations

from PySide6.QtGui import QColor

from AppCore import ColorPalette


def is_dark_theme() -> bool:
    """按内容区背景亮度判断主题深浅（四套主题通用）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def tokens() -> dict[str, str]:
    """Tag / Chip / Avatar / Skeleton / Divider 共用的中性色阶。"""
    if is_dark_theme():
        return {
            "surface": ColorPalette.custom_dark_four,
            "surface_strong": ColorPalette.custom_bg_two,
            "skeleton": "#2f3541",
            "border": ColorPalette.custom_dark_four,
            "text": ColorPalette.custom_text_title,
            "muted": ColorPalette.custom_text_description,
            "accent": ColorPalette.custom_context_color,
        }
    return {
        "surface": "#f8fafc",
        "surface_strong": "#cbd5e1",
        "skeleton": "#dbe3ec",
        "border": "#cbd5e1",
        "text": "#334155",
        "muted": "#64748b",
        "accent": ColorPalette.custom_context_color,
    }


__all__ = ["is_dark_theme", "tokens"]
