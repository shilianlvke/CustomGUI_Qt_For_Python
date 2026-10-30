"""统一按钮组件（复刻 PrimeVue Aura Button）。

覆盖 Sakai 按钮页的全部形态：severity × variant（solid/outlined/text/link）×
plain / rounded / raised / icon 左右 / 纯图标 / loading / disabled / 三种尺寸。

绘制约定：与 ``CLeftMenuButton`` 一致，**自绘 paintEvent**、颜色实时读调色板，
不缓存颜色值，主题切换后重绘即生效。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QPushButton, QSizePolicy

from AppCore import AppSettings

from ..icon_utils import render_icon
from .severity import Severity, Variant, colors_for, normalize_severity


@dataclass(frozen=True)
class _SizeSpec:
    """一档尺寸的几何参数（对齐 Aura：md 高 2.5rem）。"""

    height: int
    padding_x: int
    font_px: int
    icon_px: int


_SIZES = {
    "sm": _SizeSpec(height=32, padding_x=10, font_px=14, icon_px=14),
    "md": _SizeSpec(height=40, padding_x=12, font_px=16, icon_px=16),
    "lg": _SizeSpec(height=48, padding_x=14, font_px=18, icon_px=18),
}

_RADIUS = 6
_ICON_GAP = 8
_SPINNER_INTERVAL = 30


class CButton(QPushButton):
    """PrimeVue Aura 风格按钮。"""

    #: 内容按钮的点击信号（QPushButton.clicked 保持可用，二者等价）
    activated = Signal()

    def __init__(
        self,
        text: str = "",
        icon: str | QIcon | None = None,
        icon_pos: str = "left",
        severity: str | Severity = Severity.PRIMARY,
        variant: str | Variant = Variant.SOLID,
        plain: bool = False,
        rounded: bool = False,
        raised: bool = False,
        size: str = "md",
        loading: bool = False,
        fixed_width: int | None = None,
        border_visible: bool = True,
        corners: tuple[bool, bool, bool, bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CButton_PushButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._severity = normalize_severity(severity)
        self._variant = Variant(variant)
        self._plain = plain
        self._rounded = rounded
        self._raised = raised
        self._size = size if size in _SIZES else "md"
        self._icon_pos = icon_pos
        self._loading = loading
        self._fixed_width = fixed_width
        self._border_visible = border_visible
        self._corners = corners or (True, True, True, True)
        self._divider = False
        self._state = "normal"
        self._display_state = "normal"
        self._from_state = "normal"
        self._progress = 1.0
        self._transition: QVariantAnimation | None = None

        self._icon_source: str | None = None
        self._icon_object: QIcon | None = None
        self._spinner_angle = 0
        self._spinner_timer: QTimer | None = None

        self._apply_size()
        self.setText(text)
        self.set_icon(icon)
        self.clicked.connect(self.activated.emit)

    # ------------------------------------------------------------------
    # 尺寸与字体
    # ------------------------------------------------------------------
    @property
    def _spec(self) -> _SizeSpec:
        return _SIZES[self._size]

    def _apply_size(self) -> None:
        spec = self._spec
        font = QFont(self.font())
        font.setFamily(AppSettings.family)
        font.setPixelSize(spec.font_px)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)
        self.setFixedHeight(spec.height)
        self.updateGeometry()

    def set_size(self, size: str) -> None:
        """切换尺寸（sm / md / lg）。"""
        self._size = size if size in _SIZES else "md"
        self._apply_size()
        self.update()

    def set_severity(self, severity: str | Severity) -> None:
        self._severity = normalize_severity(severity)
        self.update()

    def set_variant(self, variant: str | Variant) -> None:
        self._variant = Variant(variant)
        self.update()

    def set_rounded(self, rounded: bool) -> None:
        self._rounded = rounded
        self.update()

    def set_raised(self, raised: bool) -> None:
        self._raised = raised
        self.update()

    def set_plain(self, plain: bool) -> None:
        self._plain = plain
        self.update()

    def set_border_visible(self, visible: bool) -> None:
        self._border_visible = visible
        self.update()

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        """按 (左上, 右上, 右下, 左下) 指定哪些角保留圆角（按钮组用）。"""
        self._corners = corners
        self.update()

    # ------------------------------------------------------------------
    # 图标与文本
    # ------------------------------------------------------------------
    def set_icon(self, icon: str | QIcon | None) -> None:
        self._icon_source = icon if isinstance(icon, str) else None
        self._icon_object = icon if isinstance(icon, QIcon) else None
        self.updateGeometry()
        self.update()

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        super().setText(text)
        self.updateGeometry()

    def _has_icon(self) -> bool:
        return self._icon_source is not None or self._icon_object is not None

    def _tinted_icon(self, color: QColor) -> QPixmap | None:
        """按当前文字色给图标着色；render_icon 按 dpr 栅格化并统一缓存。"""
        if not self._has_icon():
            return None
        source = self._icon_object if self._icon_object is not None else self._icon_source
        return render_icon(source, color, self._spec.icon_px, self.devicePixelRatioF())

    # ------------------------------------------------------------------
    # 尺寸建议
    # ------------------------------------------------------------------
    def _content_size(self) -> QSize:
        spec = self._spec
        if self._fixed_width is not None:
            return QSize(self._fixed_width, spec.height)
        if not self.text() and self._has_icon():
            return QSize(spec.height, spec.height)  # 纯图标：正方形
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self.text()) if self.text() else 0
        icon_width = spec.icon_px if self._has_icon() else 0
        gap = _ICON_GAP if (text_width and icon_width) else 0
        return QSize(spec.padding_x * 2 + icon_width + gap + text_width, spec.height)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self._content_size()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self._content_size()

    # ------------------------------------------------------------------
    # loading
    # ------------------------------------------------------------------
    def set_loading(self, loading: bool) -> None:
        if self._loading == loading:
            return
        self._loading = loading
        if loading:
            if self._spinner_timer is None:
                self._spinner_timer = QTimer(self)
                self._spinner_timer.timeout.connect(self._tick_spinner)
            self._spinner_timer.start(_SPINNER_INTERVAL)
        elif self._spinner_timer is not None:
            self._spinner_timer.stop()
        self.update()

    def is_loading(self) -> bool:
        return self._loading

    def variant(self) -> Variant:
        return self._variant

    def severity(self) -> Severity:
        return self._severity

    def set_divider(self, visible: bool) -> None:
        """在按钮左侧画一条分隔线（分体按钮用）。"""
        self._divider = visible
        self.update()

    def _tick_spinner(self) -> None:
        self._spinner_angle = (self._spinner_angle + 24) % 360
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _visual_state(self) -> str:
        if not self.isEnabled():
            return "normal"
        return self._state

    def _colors(self):
        return colors_for(self._severity, self._variant, self._plain)

    def _radius(self) -> float:
        return self.height() / 2 if self._rounded else _RADIUS

    def _rounded_path(self, rect: QRectF) -> QPainterPath:
        radius = self._radius()
        tl, tr, br, bl = (radius if flag else 0.0 for flag in self._corners)
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

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = self._colors()
        state = self._visual_state()

        if self._transition is not None and self._progress < 1.0:
            # 悬停/按下颜色过渡：在起点与目标状态色之间线性插值
            start_bg, start_border, start_text = self._state_colors(self._from_state)
            end_bg, end_border, end_text = self._state_colors(self._state)
            t = self._progress
            background = self._lerp_color(start_bg, end_bg, t)
            border = self._lerp_color(start_border, end_border, t)
            text = self._lerp_color(start_text, end_text, t)
        elif state == "pressed":
            background, border, text = colors.active_background, colors.active_border, colors.active_text
        elif state == "hover":
            background, border, text = colors.hover_background, colors.hover_border, colors.hover_text
        else:
            background, border, text = colors.background, colors.border, colors.text

        if not self.isEnabled():
            painter.setOpacity(0.55)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = self._rounded_path(rect)

        # Aura 的 raised 阴影只作用于有底色的按钮；text/outlined 叠阴影会变成灰盘
        if self._raised and self.isEnabled() and self._variant is Variant.SOLID:
            for offset, alpha in ((4, 16), (2, 22), (1, 28)):
                painter.fillPath(self._rounded_path(QRectF(rect).translated(0, offset)), QColor(0, 0, 0, alpha))

        if background.alpha() > 0:
            painter.fillPath(path, background)
        if self._border_visible and border.alpha() > 0 and self._variant is not Variant.SOLID:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(border, 1))
            painter.drawPath(path)

        if self._divider:
            divider_x = rect.left() + 0.5
            divider_color = QColor(background)
            divider_color = divider_color.darker(118) if divider_color.lightness() > 90 else divider_color.lighter(135)
            painter.setPen(QPen(divider_color, 1))
            painter.drawLine(int(divider_x), int(rect.top() + 6), int(divider_x), int(rect.bottom() - 6))

        if self._loading:
            self._paint_spinner(painter, text)
        else:
            self._paint_content(painter, text)

        if self.hasFocus() and self.isEnabled() and not self._loading:
            inner = QRectF(rect).adjusted(1, 1, -1, -1)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(text, 1, Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(self._rounded_path(inner))

        painter.end()

    def _paint_content(self, painter: QPainter, color: QColor) -> None:
        text = self.text()
        spec = self._spec
        icon_width = spec.icon_px if self._has_icon() else 0
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(text) if text else 0
        gap = _ICON_GAP if (text_width and icon_width) else 0
        total = icon_width + gap + text_width
        x = (self.width() - total) / 2
        center_y = self.height() / 2

        if self._has_icon() and self._icon_pos == "left":
            pixmap = self._tinted_icon(color)
            if pixmap is not None:
                painter.drawPixmap(int(x), int(center_y - pixmap.height() / 2), pixmap)
            x += icon_width + gap

        if text:
            painter.setPen(color)
            painter.drawText(QRectF(x, 0, text_width + 2, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            x += text_width + gap

        if self._has_icon() and self._icon_pos == "right":
            pixmap = self._tinted_icon(color)
            if pixmap is not None:
                painter.drawPixmap(int(x), int(center_y - pixmap.height() / 2), pixmap)

        if self._variant is Variant.LINK and self._state in ("hover", "pressed"):
            underline_y = center_y + spec.font_px * 0.72
            painter.setPen(QPen(color, 1))
            start = (self.width() - text_width) / 2
            painter.drawLine(int(start), int(underline_y), int(start + text_width), int(underline_y))

    def _paint_spinner(self, painter: QPainter, color: QColor) -> None:
        radius = self._spec.icon_px / 2
        center_x = self.width() / 2
        center_y = self.height() / 2
        rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, int(-self._spinner_angle * 16), int(270 * 16))

    # ------------------------------------------------------------------
    # 交互状态
    # ------------------------------------------------------------------
    def _state_colors(self, state: str) -> tuple[QColor, QColor, QColor]:
        colors = self._colors()
        if state == "pressed":
            return colors.active_background, colors.active_border, colors.active_text
        if state == "hover":
            return colors.hover_background, colors.hover_border, colors.hover_text
        return colors.background, colors.border, colors.text

    def _hover_duration(self) -> int:
        try:
            return int(AppSettings.button.hover_duration)
        except Exception:  # 配置上下文未就绪时的兜底值
            return 160

    def _lerp_color(self, start: QColor, end: QColor, t: float) -> QColor:
        return QColor(
            round(start.red() + (end.red() - start.red()) * t),
            round(start.green() + (end.green() - start.green()) * t),
            round(start.blue() + (end.blue() - start.blue()) * t),
            round(start.alpha() + (end.alpha() - start.alpha()) * t),
        )

    def _set_state(self, state: str) -> None:
        """切换视觉状态；悬停/按下按配置时长做颜色过渡。"""
        if state == self._state:
            return
        self._stop_transition()
        self._from_state = self._display_state
        self._state = state
        duration = self._hover_duration()
        if duration <= 0 or not self.isVisible():
            self._display_state = state
            self._progress = 1.0
            self.update()
            return
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(duration)
        animation.valueChanged.connect(self._on_transition_tick)
        animation.finished.connect(lambda: self._finish_transition(state))
        self._progress = 0.0
        animation.start()
        self._transition = animation

    def _on_transition_tick(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    def _finish_transition(self, state: str) -> None:
        self._stop_transition()
        self._display_state = state
        self._progress = 1.0
        self.update()

    def _stop_transition(self) -> None:
        if self._transition is not None:
            self._transition.stop()
            self._transition.deleteLater()
            self._transition = None

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self.isEnabled() and not self._loading:
            self._set_state("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._set_state("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._loading or not self.isEnabled():
            return
        self._set_state("pressed")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._loading or not self.isEnabled():
            return
        self._set_state("hover" if self.underMouse() else "normal")
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (event.Type.EnabledChange, event.Type.StyleChange):
            self._stop_transition()
            self._state = "normal"
            self._display_state = "normal"
            self._from_state = "normal"
            self._progress = 1.0
            self.update()


__all__ = ["CButton"]
