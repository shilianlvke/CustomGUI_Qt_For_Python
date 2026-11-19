"""页面自绘件：过渡模块，P7 会逐个替换为 ``guicore`` 组件。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from sllkgui.appcore import AppSettings, ColorPalette, get_theme_manager
from sllkgui.guicore.custom_ui.icon_utils import render_icon
from sllkgui.guicore.custom_ui.panels.style import RADIUS, paint_surface, panel_colors, rounded_path

from .theme import _MONO_FAMILIES, _ROLE_SIZES, _card_rect, _font, _hover_color, _line_color, _surface_color, _tint


class _ThemedLabel(QLabel):
    """按角色取色的文本标签；主题切换时自动刷新颜色。"""

    def __init__(self, text: str = "", role: str = "body", mono: bool = False, parent=None) -> None:
        super().__init__(text, parent)
        self._role = role
        family = _MONO_FAMILIES[0] if mono else AppSettings.family
        weight = QFont.Weight.DemiBold if role in {"eyebrow", "title", "section", "metric", "entry"} else QFont.Weight.Normal
        self.setFont(QFont(family, _ROLE_SIZES.get(role, 10), weight))
        self._apply_theme()
        try:
            get_theme_manager().subscribe(self._apply_theme)
        except Exception:  # noqa: BLE001 - 无主题管理器时保持初始配色
            pass

    def _apply_theme(self) -> None:
        color = {
            "eyebrow": ColorPalette.custom_context_color,
            "title": ColorPalette.custom_text_title,
            "section": ColorPalette.custom_text_title,
            "metric": ColorPalette.custom_text_title,
            "entry": ColorPalette.custom_text_title,
            "muted": ColorPalette.custom_text_description,
            "value": ColorPalette.custom_text_foreground,
            "body": ColorPalette.custom_text_foreground,
        }.get(self._role, ColorPalette.custom_text_foreground)
        self.setStyleSheet(f"color: {color}; background: transparent;")


class _Panel(QFrame):
    """py-rm Card 风格容器：圆角 + 明显描边 + 分层底色。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(painter, _card_rect(self), RADIUS, background=_surface_color(), border=_line_color())
        painter.end()


class _Chip(QWidget):
    """胶囊标签：版本、状态、来源、权限共用。"""

    def __init__(self, text: str, *, accent: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._accent = accent
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._resize_to_text()

    def _font(self) -> QFont:
        return _font(self.font(), 10, QFont.Weight.Medium)

    def _resize_to_text(self) -> None:
        width = QFontMetrics(self._font()).horizontalAdvance(self._text) + 16
        self.setFixedWidth(max(28, width))

    def set_text(self, text: str, *, accent: bool | None = None) -> None:
        self._text = text
        if accent is not None:
            self._accent = accent
        self._resize_to_text()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = _tint(colors["accent"], 38) if self._accent else None
        border = _tint(colors["accent"], 110) if self._accent else QColor(colors["border"])
        paint_surface(painter, rect, 10, background=background, border=border)
        painter.setFont(self._font())
        painter.setPen(QColor(colors["accent"] if self._accent else colors["muted"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class _ElidedLabel(QWidget):
    """单行省略文本：用于 ID、commit、URL 与简介。"""

    def __init__(self, text: str = "", *, mono: bool = False, size: int = 10, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._mono = mono
        self._size = size
        self.setFixedHeight(size + 6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setFont(_font(self.font(), self._size, mono=self._mono))
        painter.setPen(QColor(colors["muted"]))
        metrics = QFontMetrics(painter.font())
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(self._text, Qt.TextElideMode.ElideRight, max(0, self.width())),
        )
        painter.end()


#: 插件自带图标（彩色 SVG/PNG）的位图缓存（键：路径、像素尺寸、像素比）
_PLUGIN_ICON_CACHE: dict[tuple[str, int, float], QPixmap] = {}


def _plugin_icon_pixmap(path: str, size: int, dpr: float) -> QPixmap | None:
    """按设备像素比加载插件图标文件；缺失或解析失败返回 None。"""
    if not path:
        return None
    ratio = max(1.0, float(dpr))
    target = max(1, round(size * ratio))
    key = (path, target, round(ratio, 2))
    cached = _PLUGIN_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    icon = QIcon(path)
    if icon.isNull():
        return None
    pixmap = icon.pixmap(QSize(target, target))
    if pixmap.isNull():
        return None
    pixmap.setDevicePixelRatio(ratio)
    _PLUGIN_ICON_CACHE[key] = pixmap
    return pixmap


class _IconTile(QWidget):
    """条目/详情页的产品图标：强调色淡底 + 单色图标或插件自带图标。"""

    def __init__(self, icon: str, size: int = 38, parent=None, *, icon_file: str = "") -> None:
        super().__init__(parent)
        self._icon = icon
        self._icon_file = icon_file
        self._size = max(24, int(size))
        self.setFixedSize(self._size, self._size)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        accent = QColor(colors["accent"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 12 if self._size >= 48 else 10)
        fill = QColor(accent)
        fill.setAlpha(30)
        painter.fillPath(path, fill)
        border = QColor(accent)
        border.setAlpha(85)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        inner = self._size - 16
        pixmap = _plugin_icon_pixmap(self._icon_file, inner, self.devicePixelRatioF())
        if pixmap is None:
            pixmap = render_icon(self._icon, QColor(colors["text"]), inner, self.devicePixelRatioF())
        if pixmap is not None and not pixmap.isNull():
            dpr = pixmap.devicePixelRatio() or 1.0
            width = pixmap.width() / dpr
            height = pixmap.height() / dpr
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()


class _ModeCard(QFrame):
    """左侧模式导轨：自绘图标、标题与计数。"""

    clicked = Signal(str)

    def __init__(self, mode: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.title = title
        self._count = 0
        self._active = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_count(self, count: int) -> None:
        self._count = max(0, int(count))
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.mode)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = None
        border = None
        if self._active:
            background = _tint(colors["accent"], 34)
            border = _tint(colors["accent"], 96)
        elif self._hovered:
            background = _hover_color()
        paint_surface(painter, rect, 10, background=background, border=border)

        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["accent"]))
            painter.drawRoundedRect(QRectF(rect.left() + 1, rect.top() + 13, 3, rect.height() - 26), 1.5, 1.5)

        glyph = QRectF(rect.left() + 14, rect.center().y() - 9, 18, 18)
        self._draw_glyph(painter, glyph, QColor(colors["accent"] if self._active else colors["muted"]))
        painter.setFont(_font(self.font(), 13, QFont.Weight.DemiBold if self._active else QFont.Weight.Medium))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(rect.left() + 42, rect.top(), rect.width() - 84, rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        painter.setFont(_font(self.font(), 11))
        painter.setPen(QColor(colors["accent"] if self._active else colors["muted"]))
        painter.drawText(
            QRectF(rect.right() - 44, rect.top(), 32, rect.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            str(self._count),
        )
        painter.end()

    def _draw_glyph(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = rect.left()
        top = rect.top()
        width = rect.width()
        if self.mode == "installed":
            for index in range(3):
                painter.drawRoundedRect(QRectF(left, top + index * 6.4, width, 3.4), 1.7, 1.7)
            return
        if self.mode == "discover":
            painter.drawEllipse(QRectF(left + 1, top + 1, 11, 11))
            handle = QRectF(left + 10, top + 10, 6, 6)
            painter.drawLine(handle.topLeft(), handle.bottomRight())
            return
        for index in range(3):
            painter.drawEllipse(QRectF(left, top + index * 6.2, width, 4.2))


class _StatTile(QFrame):
    """顶部指标卡：参考 py-rm MetricCard（说明在上、数值在下）。"""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.caption = caption
        self._value = "0"
        self.setFixedSize(104, 66)

    def set_value(self, value: int | str) -> None:
        self._value = str(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = _card_rect(self)
        paint_surface(painter, rect, RADIUS, background=_surface_color(), border=_line_color())
        painter.setFont(_font(self.font(), 9))
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 10, rect.width() - 28, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.caption,
        )
        painter.setFont(_font(self.font(), 22, QFont.Weight.DemiBold, mono=True))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 27, rect.width() - 28, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._value,
        )
        painter.end()


# ----------------------------------------------------------------------
# DataView 条目
