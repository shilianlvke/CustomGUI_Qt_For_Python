"""面板族共用配色、绘制与配置读取。"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from AppCore import AppSettings, ColorPalette

from ..display.palette import is_dark_theme, tokens

#: 面板圆角（对齐 Aura 的 6px，桌面端略放大一档）
RADIUS = 8


def panel_settings() -> tuple[int, int, int, int]:
    """(标签滑动时长, 折叠时长, 分割条宽度, 握把长度)。"""
    try:
        cfg = AppSettings.panels
        return (
            int(cfg.tab_duration),
            int(cfg.collapse_duration),
            int(cfg.splitter_handle),
            int(cfg.splitter_grip),
        )
    except Exception:  # 配置上下文未就绪时用兜底值，组件不应因此不可用
        return 180, 180, 8, 28


def panel_colors() -> dict[str, str]:
    """当前主题下的面板族配色（切主题重绘即生效）。"""
    base = tokens()
    if is_dark_theme():
        return {
            "background": ColorPalette.custom_bg_one,
            "header": ColorPalette.custom_dark_one,
            "hover": ColorPalette.custom_dark_three,
            "border": base["border"],
            "divider": base["border"],
            "text": base["text"],
            "muted": base["muted"],
            "accent": base["accent"],
            "track": "#3f3f46",
            "on_accent": "#ffffff",
        }
    return {
        "background": "#ffffff",
        "header": "#f8fafc",
        "hover": "#f1f5f9",
        "border": "#e2e8f0",
        "divider": "#e2e8f0",
        "text": "#334155",
        "muted": "#64748b",
        "accent": ColorPalette.custom_context_color,
        "track": "#cbd5e1",
        "on_accent": "#ffffff",
    }


def with_alpha(color: QColor | str, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(max(0, min(255, alpha)))
    return value


def rounded_path(rect: QRectF, radius: float = RADIUS) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def paint_surface(
    painter: QPainter,
    rect: QRectF,
    radius: float = RADIUS,
    background: QColor | str | None = None,
    border: QColor | str | None = None,
) -> QPainterPath:
    """画一层圆角面板（底色 + 1px 描边），返回路径供裁剪用。"""
    colors = panel_colors()
    path = rounded_path(rect, radius)
    painter.fillPath(path, QColor(background or colors["background"]))
    if border is not None:
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawPath(path)
    return path


def panel_font(size: int = 13, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    font = QFont(AppSettings.family)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


__all__ = [
    "RADIUS",
    "panel_colors",
    "panel_font",
    "panel_settings",
    "paint_surface",
    "rounded_path",
    "with_alpha",
]
