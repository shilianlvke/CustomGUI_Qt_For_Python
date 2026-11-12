"""面板族共用配色、绘制与配置读取。"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from sllkgui.appcore import AppSettings, ColorPalette

from ...acrylic import acrylic_active, glass_surface, glass_tint
from ..display.palette import is_dark_theme, tokens

#: 面板圆角（对齐 Aura 的 6px，桌面端略放大一档）
RADIUS = 8


def panel_radius() -> float:
    """面板圆角，配置缺失时回落默认值。"""
    try:
        return float(AppSettings.panels.radius)
    except Exception:
        return RADIUS


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


def panel_colors() -> dict[str, str | QColor]:
    """当前主题下的面板族配色（切主题重绘即生效）。

    亚克力模式下背景/描边与 ``#CCard_Frame`` 同一套半透明写法：面板是画在
    卡片上的自绘表面，若继续用不透明底色，会在玻璃卡片上留下实色补丁。
    文字色仍返回字符串（部分调用点直接拼进 ``setStyleSheet``）。
    """
    base = tokens()
    glass = acrylic_active()
    # 延迟导入，避免 panels -> button -> ... -> panels 的循环依赖
    from ..button.severity import contrast_text

    on_accent = contrast_text(QColor(base["accent"]))
    if is_dark_theme():
        return {
            "background": glass_surface(ColorPalette.custom_bg_one, 0.34, minimum=0.10) if glass else ColorPalette.custom_bg_one,
            "header": glass_surface(ColorPalette.custom_dark_one, 0.10, minimum=0.04) if glass else ColorPalette.custom_dark_one,
            "header_solid": ColorPalette.custom_dark_one,
            "hover": glass_surface(ColorPalette.custom_dark_three, 0.14, minimum=0.05) if glass else ColorPalette.custom_dark_three,
            "border": glass_tint(base["border"], 0.55) if glass else base["border"],
            "divider": glass_tint(base["border"], 0.35) if glass else base["border"],
            "text": base["text"],
            "muted": base["muted"],
            "accent": base["accent"],
            "track": glass_surface(ColorPalette.custom_dark_four, 0.55, minimum=0.15) if glass else ColorPalette.custom_dark_four,
            "on_accent": on_accent,
        }
    return {
        "background": glass_surface(ColorPalette.custom_dark_three, 0.34, minimum=0.10) if glass else ColorPalette.custom_dark_three,
        "header": glass_surface(ColorPalette.custom_dark_two, 0.10, minimum=0.04) if glass else ColorPalette.custom_dark_two,
        "header_solid": ColorPalette.custom_dark_two,
        "hover": glass_surface(ColorPalette.custom_dark_four, 0.14, minimum=0.05) if glass else ColorPalette.custom_dark_four,
        "border": glass_tint(ColorPalette.custom_bg_two, 0.55) if glass else ColorPalette.custom_bg_two,
        "divider": glass_tint(ColorPalette.custom_bg_two, 0.35) if glass else ColorPalette.custom_bg_two,
        "text": ColorPalette.custom_text_title,
        "muted": ColorPalette.custom_text_description,
        "accent": ColorPalette.custom_context_color,
        "track": glass_surface(ColorPalette.custom_bg_three, 0.55, minimum=0.15) if glass else ColorPalette.custom_bg_three,
        "on_accent": on_accent,
    }


def qss_color(value: str | QColor) -> str:
    """把配色值转成 QSS 可解析的颜色字符串。

    ``panel_colors()`` 在亚克力模式下返回带 alpha 的 :class:`QColor`（自绘
    ``fillRect`` 需要它），但 Qt 样式表不认 ``QColor`` 的 Python 字符串形式，
    直接插进 QSS 会得到无效颜色、整条规则被丢弃。QSS 侧统一走这里转成
    ``rgba(r, g, b, a)`` 写法（alpha 取 0-255，与 ``Styles._rgba`` 一致）。
    """
    color = value if isinstance(value, QColor) else QColor(value)
    if not color.isValid():
        return "transparent"
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def with_alpha(color: QColor | str, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(max(0, min(255, alpha)))
    return value


def rounded_path(rect: QRectF, radius: float | None = None) -> QPainterPath:
    value = panel_radius() if radius is None else radius
    path = QPainterPath()
    path.addRoundedRect(rect, value, value)
    return path


def paint_surface(
    painter: QPainter,
    rect: QRectF,
    radius: float | None = None,
    background: QColor | str | None = None,
    border: QColor | str | None = None,
) -> QPainterPath:
    """画一层圆角面板（底色 + 1px 描边），返回路径供裁剪用。"""
    colors = panel_colors()
    path = rounded_path(rect, panel_radius() if radius is None else radius)
    painter.fillPath(path, QColor(background or colors["background"]))
    if border is not None:
        painter.setBrush(QColor(ColorPalette.custom_transparent))
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
    "panel_radius",
    "panel_colors",
    "panel_font",
    "panel_settings",
    "paint_surface",
    "qss_color",
    "rounded_path",
    "with_alpha",
]
