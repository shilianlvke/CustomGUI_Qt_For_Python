"""统一按钮组件（复刻 PrimeVue Aura Button）。

覆盖 Sakai 按钮页的全部形态：severity × variant（solid/outlined/text/link）×
plain / rounded / raised / icon 左右 / 纯图标 / loading / disabled / 三种尺寸。

绘制约定：与 ``CLeftMenuButton`` 一致，**自绘 paintEvent**、颜色实时读调色板，
不缓存颜色值，主题切换后重绘即生效。

几处与 Aura 对齐的细节：

1. ``raised`` 的阴影是 CSS ``box-shadow``，会溢出按钮盒子——Qt 的绘制被裁剪在
   控件矩形内，所以 raised 按钮额外留出 :data:`~..paint_utils.SHADOW_MARGINS` 的透明边距，
   真正的外框画在缩小后的「body」矩形里，外观尺寸与普通按钮一致；
2. 底色用整块 body 矩形填充（只有描边内缩 0.5px 保证 1px 线清晰），这样按钮组、
   分体按钮的相邻分段之间不会露出 1px 的缝隙；
3. 焦点框只在**键盘聚焦**时出现（等效 CSS 的 ``:focus-visible``），鼠标点击不画；
4. ``loading`` 时 spinner 占据前置图标位、文字保留（Aura 的 Button 就是这么排的），
   转速 2s/圈与 ``.p-icon-spin`` 一致。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QPushButton, QSizePolicy

from customgui.appcore import AppSettings

from ..icon_utils import render_icon
from ..paint_utils import SHADOW_MARGINS, shadow_layers
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

#: spinner 转一圈的时长（对齐 Aura 的 ``.p-icon-spin`` 2s linear）
_SPIN_PERIOD_MS = 2000
_SPIN_INTERVAL_MS = 16

#: 禁用态整体透明度（对齐 Aura 的 ``disabled.opacity: 0.6``）
_DISABLED_OPACITY = 0.6


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
        icon_size: int | None = None,
        focus_ring: bool = True,
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
        self._icon_size = icon_size
        self._focus_ring = focus_ring
        self._focus_visible = False
        self._state = "normal"
        #: 过渡中「当前实际画出来的颜色」；None 表示还没有画过（首次绘制前）
        self._current_colors: tuple[QColor, QColor, QColor] | None = None
        self._transition: QVariantAnimation | None = None
        #: 供外部观察的两个只读状态：过渡结束时所处状态 / 当前进度
        self._display_state = "normal"
        self._progress = 1.0

        self._icon_source: str | None = None
        self._icon_object: QIcon | None = None
        self._spinner_angle = 0.0
        self._spinner_timer: QTimer | None = None

        self._shadow_cache_key: tuple | None = None
        self._shadow_cache: list[tuple[QPainterPath, QColor]] = []

        self._apply_size()
        self.setText(text)
        self.set_icon(icon)
        if loading:
            self._start_spinner()
        self.clicked.connect(self.activated.emit)

    # ------------------------------------------------------------------
    # 尺寸与字体
    # ------------------------------------------------------------------
    @property
    def _spec(self) -> _SizeSpec:
        return _SIZES[self._size]

    def _icon_px(self) -> int:
        return self._icon_size if self._icon_size else self._spec.icon_px

    def _margins(self) -> tuple[int, int, int, int]:
        """raised 阴影需要的透明边距：(左, 上, 右, 下)。"""
        return SHADOW_MARGINS if self._raised else (0, 0, 0, 0)

    def _body_rect(self) -> QRectF:
        """真正画按钮的那块矩形（raised 时比控件小一圈，余量留给阴影）。"""
        left, top, right, bottom = self._margins()
        return QRectF(self.rect()).adjusted(left, top, -right, -bottom)

    def _apply_size(self) -> None:
        spec = self._spec
        font = QFont(self.font())
        font.setFamily(AppSettings.family)
        font.setPixelSize(spec.font_px)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)
        _, top, _, bottom = self._margins()
        self.setFixedHeight(spec.height + top + bottom)
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
        self._invalidate_shadow()
        self.update()

    def set_raised(self, raised: bool) -> None:
        self._raised = raised
        self._invalidate_shadow()
        self._apply_size()
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
        self._invalidate_shadow()
        self.update()

    def set_focus_ring(self, visible: bool) -> None:
        """关闭/开启键盘聚焦时的焦点框（鼠标点击本来就不画）。"""
        self._focus_ring = visible
        self.update()

    def set_icon_size(self, size: int | None) -> None:
        """覆盖图标逻辑尺寸（默认取当前尺寸档的 icon_px）。"""
        self._icon_size = size
        self.updateGeometry()
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
        self.update()

    def _has_icon(self) -> bool:
        return self._icon_source is not None or self._icon_object is not None

    def _tinted_icon(self, color: QColor) -> QPixmap | None:
        """按当前文字色给图标着色；render_icon 按 dpr 栅格化并统一缓存。"""
        if not self._has_icon():
            return None
        source = self._icon_object if self._icon_object is not None else self._icon_source
        return render_icon(source, color, self._icon_px(), self.devicePixelRatioF())

    # ------------------------------------------------------------------
    # 尺寸建议
    # ------------------------------------------------------------------
    def _content_size(self) -> QSize:
        spec = self._spec
        left, top, right, bottom = self._margins()
        icon_px = self._icon_px()
        text = self.text()
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(text) if text else 0
        leading = icon_px if (self._loading or (self._has_icon() and self._icon_pos == "left")) else 0
        trailing = icon_px if (self._has_icon() and self._icon_pos == "right" and not self._loading) else 0
        gap = _ICON_GAP if text_width and (leading or trailing) else 0
        content = leading + trailing + text_width + (gap if text_width else 0)
        if self._fixed_width is not None:
            width = self._fixed_width
        elif not text and self._has_icon():
            width = spec.height  # 纯图标：正方形（对齐 Aura 的 icon-only width）
        else:
            width = spec.padding_x * 2 + content
        return QSize(width + left + right, spec.height + top + bottom)

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
            self._start_spinner()
        elif self._spinner_timer is not None:
            self._spinner_timer.stop()
        # 文字按钮进入 loading 时会多出前置 spinner，宽度要跟着变
        self.updateGeometry()
        self.update()

    def _start_spinner(self) -> None:
        if self._spinner_timer is None:
            self._spinner_timer = QTimer(self)
            self._spinner_timer.timeout.connect(self._tick_spinner)
        self._spinner_timer.start(_SPIN_INTERVAL_MS)

    def is_loading(self) -> bool:
        return self._loading

    def variant(self) -> Variant:
        return self._variant

    def severity(self) -> Severity:
        return self._severity

    def _tick_spinner(self) -> None:
        step = 360.0 * _SPIN_INTERVAL_MS / _SPIN_PERIOD_MS
        self._spinner_angle = (self._spinner_angle + step) % 360.0
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
        return self._body_rect().height() / 2 if self._rounded else _RADIUS

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

    def _invalidate_shadow(self) -> None:
        self._shadow_cache_key = None
        self._shadow_cache = []

    def _shadow_layers(self) -> list[tuple[QPainterPath, QColor]]:
        """raised 阴影：预先裁掉按钮本体，只留外圈，避免叠成灰盘。"""
        body = self._body_rect()
        key = (round(body.width()), round(body.height()), round(self._radius()), self._corners)
        if self._shadow_cache_key == key:
            return self._shadow_cache
        self._shadow_cache = shadow_layers(self._rounded_path(body), body, self._radius())
        self._shadow_cache_key = key
        return self._shadow_cache

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = self._colors()
        state = self._visual_state()

        if self._transition is not None and self._current_colors is not None:
            # 过渡中：直接用动画算好的当前颜色（起点是「上次画出来的颜色」，
            # 所以中途改变方向也不会跳变）
            background, border, text = self._current_colors
        elif state == "pressed":
            background, border, text = colors.active_background, colors.active_border, colors.active_text
        elif state == "hover":
            background, border, text = colors.hover_background, colors.hover_border, colors.hover_text
        else:
            background, border, text = colors.background, colors.border, colors.text
        self._current_colors = (background, border, text)

        if not self.isEnabled():
            painter.setOpacity(_DISABLED_OPACITY)

        body = self._body_rect()
        path = self._rounded_path(body)

        # Aura 的 raised 阴影对四种 variant 都生效（Sakai 的 Rounded Text 就是靠它立起来的）
        if self._raised:
            for layer, color in self._shadow_layers():
                painter.fillPath(layer, color)

        # 底色铺满整个 body：相邻分段（按钮组 / 分体按钮）不会露出 1px 缝
        if background.alpha() > 0:
            painter.fillPath(path, background)
        if self._border_visible and border.alpha() > 0 and self._variant is not Variant.SOLID:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(border, 1))
            painter.drawPath(self._rounded_path(QRectF(body).adjusted(0.5, 0.5, -0.5, -0.5)))

        self._paint_content(painter, text, body)

        # 焦点框只给键盘聚焦（等效 CSS :focus-visible），鼠标点击不出现
        if self._focus_visible and self._focus_ring and self.isEnabled() and not self._loading:
            inner = QRectF(body).adjusted(1.5, 1.5, -1.5, -1.5)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(text, 1.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(self._rounded_path(inner))

        painter.end()

    def _paint_content(self, painter: QPainter, color: QColor, body: QRectF) -> None:
        spec = self._spec
        text = self.text()
        icon_px = self._icon_px()
        leading_icon = not self._loading and self._has_icon() and self._icon_pos == "left"
        trailing_icon = not self._loading and self._has_icon() and self._icon_pos == "right"
        leading = icon_px if (self._loading or leading_icon) else 0
        trailing = icon_px if trailing_icon else 0

        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(text) if text else 0
        gap = _ICON_GAP if (text_width and (leading or trailing)) else 0
        total = leading + trailing + text_width + (gap if text_width else 0)
        x = body.left() + (body.width() - total) / 2
        center_y = body.center().y()

        if self._loading:
            self._paint_spinner(painter, color, x, icon_px, center_y)
            x += leading + gap
        elif leading_icon:
            pixmap = self._tinted_icon(color)
            if pixmap is not None:
                painter.drawPixmap(int(x), int(center_y - pixmap.height() / 2), pixmap)
            x += leading + gap

        if text:
            painter.setPen(color)
            painter.drawText(
                QRectF(x, body.top(), text_width + 2, body.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                text,
            )
            x += text_width + gap

        if trailing_icon:
            pixmap = self._tinted_icon(color)
            if pixmap is not None:
                painter.drawPixmap(int(x), int(center_y - pixmap.height() / 2), pixmap)

        # Aura：link 变体只在 hover 时给文字加下划线
        if self._variant is Variant.LINK and self._state == "hover" and text:
            underline_y = center_y + spec.font_px * 0.72
            start = body.center().x() - text_width / 2
            painter.setPen(QPen(color, 1))
            painter.drawLine(int(start), int(underline_y), int(start + text_width), int(underline_y))

    def _paint_spinner(self, painter: QPainter, color: QColor, x: float, size: int, center_y: float) -> None:
        radius = (size - 2) / 2
        center_x = x + size / 2
        rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap))
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
        """切换视觉状态；悬停/按下按配置时长做颜色过渡。

        过渡的**起点取上一次实际画出来的颜色**，而不是「上一个稳定状态」——
        鼠标快速划过时过渡会被打断，从稳定状态重新起算会先跳回原色再走一遍，
        观感就是「闪一下」。
        """
        if state == self._state:
            return
        start = self._current_colors or self._state_colors(self._state)
        target = self._state_colors(state)
        self._stop_transition()
        self._state = state
        duration = self._hover_duration()
        if duration <= 0 or not self.isVisible():
            self._current_colors = None
            self._display_state = state
            self._progress = 1.0
            self.update()
            return
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(duration)
        animation.valueChanged.connect(lambda value: self._on_transition_tick(value, start, target))
        animation.finished.connect(self._finish_transition)
        self._transition = animation
        self._progress = 0.0
        animation.start()

    def _on_transition_tick(self, value, start, target) -> None:
        progress = float(value)
        self._progress = progress
        self._current_colors = (
            self._lerp_color(start[0], target[0], progress),
            self._lerp_color(start[1], target[1], progress),
            self._lerp_color(start[2], target[2], progress),
        )
        self.update()

    def _finish_transition(self) -> None:
        self._stop_transition()
        self._current_colors = None  # 交还给状态色
        self._display_state = self._state
        self._progress = 1.0
        self.update()

    def _stop_transition(self) -> None:
        if self._transition is not None:
            self._transition.stop()
            self._transition.deleteLater()
            self._transition = None

    def focusInEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._focus_visible = event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._focus_visible = False
        super().focusOutEvent(event)
        self.update()

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

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        # Aura 在 loading 时把按钮置为 disabled，键盘也不该能激活
        if self._loading and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._invalidate_shadow()
        super().resizeEvent(event)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (event.Type.EnabledChange, event.Type.StyleChange):
            self._stop_transition()
            self._state = "normal"
            self._display_state = "normal"
            self._current_colors = None
            self._progress = 1.0
            self.update()


__all__ = ["CButton"]
