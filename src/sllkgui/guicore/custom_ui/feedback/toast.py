"""浮出通知（Windows Fluent Design InfoBar 风格，带堆叠与自动消失）。

本模块只负责**画**：布局、配色、进出动画、悬停暂停、进度与动作按钮。
去重、通道、溢出裁决、状态机在 :mod:`sllkgui.guicore.feedback.toast_bus`；
插件门面在 :mod:`sllkgui.gallery.toast`。

兼容性约定：``CToast.show_message(...)`` / ``CToast.clear(parent)`` 的既有签名与
行为（按窗口堆叠、``closed`` 信号）保持不变，基座以外仍在直调它的代码不会坏。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sllkgui.appcore import AppSettings, ColorPalette, Language
from sllkgui.appcore.feedback import (
    ToastAction,
    ToastDismissReason,
    ToastLevel,
    normalize_level,
)

from ...acrylic import glass_surface
from ..button.severity import Severity, normalize_severity
from ..close_button import CCloseButton as _CloseButton
from ..display.palette import tokens
from .message import _MessageIcon

#: 单条通知宽度 / 外阴影边距（配置不可用时的兜底默认）
_WIDTH = 340
_SHADOW = 5
#: 正文最多显示行数（超出折叠，避免一条错误把半屏糊住）
_MAX_TEXT_LINES = 3
#: 进度条高度
_BAR_HEIGHT = 3

#: 协议级别 → 组件语义色（``Severity``）。loading/progress 共用 info 图标，
#: 但会被替换成旋转指示或进度条。
_LEVEL_TO_SEVERITY: dict[str, str] = {
    "success": "success",
    "info": "info",
    "warn": "warn",
    "error": "danger",
    "neutral": "secondary",
    "loading": "info",
    "progress": "info",
    "danger": "danger",
    "warning": "warn",
    "critical": "danger",
}

_UNSET = object()


def _settings() -> tuple[int, int, int, int, int]:
    """(life, max, duration, margin, spacing)，配置缺失时回落到默认值。"""
    try:
        from sllkgui.appcore import AppSettings

        cfg = AppSettings.feedback
        return (
            int(cfg.toast_life),
            max(1, int(cfg.toast_max)),
            int(cfg.toast_duration),
            int(cfg.toast_margin),
            int(cfg.toast_spacing),
        )
    except Exception:
        return 3000, 4, 180, 20, 8


def _severity_for(level: str | ToastLevel) -> Severity:
    key = level.value if isinstance(level, ToastLevel) else str(level).strip().lower()
    try:
        return normalize_severity(_LEVEL_TO_SEVERITY.get(key, key))
    except ValueError:
        return Severity.INFO


class _Spinner(QWidget):
    """12px 旋转弧：``loading`` 级别替换静态图标，主题色实时生效。"""

    def __init__(self, size: int, parent=None) -> None:
        super().__init__(parent)
        self._size = max(12, int(size))
        self.setFixedSize(self._size, self._size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(tokens()["accent"]), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawArc(rect, -self._angle * 16, 270 * 16)
        painter.end()


class _ActionLabel(QLabel):
    """toast 内联动作：轻量文本按钮（不引入完整 ``CButton`` 的盒模型）。"""

    clicked = Signal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self._apply()

    def _apply(self) -> None:
        color = QColor(tokens()["accent"])
        if not self._hover:
            color.setAlpha(230)
        self.setStyleSheet(
            f"color: {color.name()}; background: transparent;"
            f" text-decoration: {'underline' if self._hover else 'none'};"
        )

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self._apply()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self._apply()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CToast(QFrame):
    """右上角通知条：滑入淡入、定时消失、同窗口自动堆叠。

    ``closed`` 保持无参信号（历史契约）；新增 ``closed_reason`` 携带关闭原因，
    供总线区分超时 / 手动 / 被挤出 / 动作 / 宿主关闭。
    """

    closed = Signal()
    closed_reason = Signal(str)
    action_triggered = Signal(str)
    #: 内容变更导致高度变化时发出（总线据此重排同锚点的其它条）
    resized = Signal()

    _stacks: dict[int, list[CToast]] = {}

    def __init__(
        self,
        parent: QWidget,
        text: str = "",
        title: str = "",
        severity: str | ToastLevel = "info",
        life: int | None = None,
        offset_top: int = 0,
        *,
        progress: float | None = None,
        actions: tuple[ToastAction, ...] = (),
        closable: bool = True,
        detail: str = "",
        toast_id: str = "",
    ):
        super().__init__(parent)
        self._level, _invalid = normalize_level(severity)
        self._severity = _severity_for(self._level)
        self._closing = False
        self._expanded = False
        self._closable = bool(closable)
        self._toast_id = toast_id
        self._actions = tuple(actions or ())
        self._progress = progress
        self._detail = str(detail or "")
        self._dismiss_reason = ToastDismissReason.MANUAL
        self._offset_top = max(0, int(offset_top))
        self._life, _, self._duration, self._margin, self._spacing = _settings()
        # 宽度与外阴影边距来自 settings（构造时读取，避免导入期触发配置加载）
        try:
            from sllkgui.appcore import AppSettings

            feedback = AppSettings.feedback
            self._width = int(feedback.toast_width)
            self._shadow = int(feedback.toast_shadow)
        except Exception:
            self._width, self._shadow = _WIDTH, _SHADOW
        if life is not None:
            self._life = max(0, int(life))

        self.setFixedWidth(self._width + self._shadow * 2)
        self.setAttribute(Qt.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14 + self._shadow, 12 + self._shadow // 2, 10 + self._shadow, 12 + self._shadow)
        layout.setSpacing(10)

        self._icon = _MessageIcon(self._severity, parent=self)
        self._spinner = _Spinner(self._icon.width(), parent=self)
        self._spinner.hide()
        layout.addWidget(self._icon, 0, Qt.AlignTop)
        layout.addWidget(self._spinner, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = QLabel(title, self)
        title_font = QFont(self.font())
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setVisible(bool(title))
        text_layout.addWidget(self._title_label)

        self._text_label = QLabel(text, self)
        self._text_label.setWordWrap(True)
        text_font = QFont(self.font())
        text_font.setPixelSize(12)
        self._text_label.setFont(text_font)
        self._text_label.setVisible(bool(text))
        text_layout.addWidget(self._text_label)

        self._action_row = QWidget(self)
        action_layout = QHBoxLayout(self._action_row)
        action_layout.setContentsMargins(0, 4, 0, 0)
        action_layout.setSpacing(14)
        self._action_row.setVisible(False)
        text_layout.addWidget(self._action_row)

        self._more_label = _ActionLabel("", self)
        more_font = QFont(self.font())
        more_font.setPixelSize(11)
        self._more_label.setFont(more_font)
        self._more_label.setVisible(False)
        self._more_label.clicked.connect(self._toggle_expanded)
        text_layout.addWidget(self._more_label, 0, Qt.AlignLeft)

        layout.addLayout(text_layout, 1)

        palette = tokens()
        self._close_button = _CloseButton(QColor(palette["muted"]), parent=self)
        self._close_button.clicked.connect(lambda: self.dismiss(ToastDismissReason.MANUAL))
        self._close_button.setVisible(self._closable)
        layout.addWidget(self._close_button, 0, Qt.AlignTop)

        self._rebuild_actions()
        self._apply_colors()
        self._apply_level_visuals()
        self._apply_text_clamp()
        self._update_more_label()
        if self._detail:
            self.setToolTip(self._detail)
            self._text_label.setToolTip(self._detail)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade: QPropertyAnimation | None = None
        self._slide: QPropertyAnimation | None = None
        self._finished = False
        #: 淡出动画在无事件循环/低帧率环境下可能不触发 finished，用定时器兜底
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._finish)

        #: 不确定进度条 / 旋转指示的相位驱动
        self._phase = 0
        self._phase_timer = QTimer(self)
        self._phase_timer.setInterval(50)
        self._phase_timer.timeout.connect(self._tick_phase)
        if self._needs_phase_timer():
            self._phase_timer.start()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self.dismiss(ToastDismissReason.TIMEOUT))
        if self._life > 0:
            self._timer.start(self._life)

        parent.installEventFilter(self)
        self._fit_height()

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def toast_id(self) -> str:
        """总线分配的稳定 id（直调 ``show_message`` 时为空串）。"""
        return self._toast_id

    def level(self) -> ToastLevel:
        return self._level

    def dismiss_reason(self) -> ToastDismissReason:
        return self._dismiss_reason

    def is_persistent(self) -> bool:
        return self._life <= 0

    def _needs_phase_timer(self) -> bool:
        return self._level in (ToastLevel.LOADING, ToastLevel.PROGRESS)

    def _tick_phase(self) -> None:
        self._phase = (self._phase + 4) % 200
        self.update()

    def _apply_colors(self) -> None:
        # 构造期间 QFrame 会先收到 StyleChange/PaletteChange，此时标签还没建好
        if not hasattr(self, "_title_label"):
            return
        palette = tokens()
        dark = QColor(palette["surface"]).lightness() < 128
        self._title_label.setStyleSheet(f"color: {palette['text']}; background: transparent;")
        self._text_label.setStyleSheet(f"color: {palette['muted']}; background: transparent;")
        self._more_label._apply()
        for child in self._action_row.findChildren(_ActionLabel):
            child._apply()
        self._card = glass_surface(
            ColorPalette.custom_bg_one if dark else ColorPalette.custom_dark_three,
            AppSettings.glass.menu,
            minimum=0.88,
        )
        self._border = QColor(palette["border"])

    def _apply_level_visuals(self) -> None:
        """``loading`` 用旋转指示替换静态图标；其余级别显示语义图标。"""
        loading = self._level is ToastLevel.LOADING
        self._spinner.setVisible(loading)
        self._icon.setVisible(not loading)
        if not loading:
            self._icon.set_severity(self._severity)

    def _rebuild_actions(self) -> None:
        layout = self._action_row.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        font = QFont(self.font())
        font.setPixelSize(11)
        for action in self._actions:
            label = _ActionLabel(action.text, self._action_row)
            label.setFont(font)
            label.clicked.connect(lambda action_id=action.action_id: self._on_action(action_id))
            layout.addWidget(label)
        self._action_row.setVisible(bool(self._actions))

    def _on_action(self, action_id: str) -> None:
        self.action_triggered.emit(action_id)
        for action in self._actions:
            if action.action_id == action_id and action.dismiss:
                self.dismiss(ToastDismissReason.ACTION)
                break

    def _fit_height(self) -> bool:
        """按当前宽度与折叠状态重算高度。

        ``QLabel`` 开启换行后 ``sizeHint`` 仍按单行宽度估算，``adjustSize()``
        不会随折叠/展开变化；这里用布局的 ``heightForWidth`` 显式定高。
        """
        layout = self.layout()
        if layout is None:
            return False
        before = self.height()
        # 先让布局丢弃上一步的缓存高度，否则 heightForWidth 仍返回折叠态结果
        layout.invalidate()
        layout.activate()
        hint = layout.heightForWidth(self.width()) if layout.hasHeightForWidth() else 0
        height = hint if hint > 0 else self.sizeHint().height()
        self.setFixedHeight(max(1, int(height)))
        return abs(int(height) - before) > 1

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._apply_text_clamp()
        self._update_more_label()
        self._fit_height()
        self.resized.emit()

    def _apply_text_clamp(self) -> None:
        if not hasattr(self, "_text_label"):
            return
        metrics = QFontMetrics(self._text_label.font())
        limit = metrics.lineSpacing() * _MAX_TEXT_LINES + 2
        self._text_label.setMaximumHeight(16777215 if self._expanded else limit)

    def _update_more_label(self) -> None:
        if not self._text_label.text():
            self._more_label.setVisible(False)
            return
        metrics = QFontMetrics(self._text_label.font())
        limit = metrics.lineSpacing() * _MAX_TEXT_LINES + 2
        width = max(120, self._width - 60)
        # 先解除高度上限再量：``heightForWidth`` 会受 maximumHeight 影响，
        # 直接量会把"需要多高"量成"被裁到多高"，展开按钮永远不出现。
        self._text_label.setMaximumHeight(16777215)
        needed = self._text_label.heightForWidth(width)
        self._apply_text_clamp()
        self._more_label.setVisible(needed > limit)
        if needed > limit:
            key = "language.UI.ui_ToastCollapse" if self._expanded else "language.UI.ui_ToastExpand"
            self._more_label.setText(str(Language.resolve_key(key, "收起" if self._expanded else "展开")))

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(
            self._shadow,
            self._shadow // 2,
            self._width,
            self.height() - self._shadow * 2,
        )

        for offset, alpha in ((3, 12), (1, 24)):
            shadow = QPainterPath()
            shadow.addRoundedRect(card.translated(0, offset), 8, 8)
            shadow_color = QColor(ColorPalette.custom_black)
            shadow_color.setAlpha(alpha)
            painter.fillPath(shadow, shadow_color)

        path = QPainterPath()
        path.addRoundedRect(card, 8, 8)
        painter.fillPath(path, self._card)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._border, 1))
        painter.drawPath(path)

        self._paint_progress(painter, card)
        painter.end()

    def _paint_progress(self, painter: QPainter, card: QRectF) -> None:
        if self._level not in (ToastLevel.PROGRESS, ToastLevel.LOADING):
            return
        track = QRectF(card.left() + 8, card.bottom() - _BAR_HEIGHT - 1, card.width() - 16, _BAR_HEIGHT)
        base = QColor(tokens()["accent"])
        track_color = QColor(base)
        track_color.setAlpha(48)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 1.5, 1.5)
        painter.setBrush(base)
        if self._progress is None:
            # 不确定进度：一段 30% 宽的滑块循环
            span = track.width() * 0.3
            offset = (track.width() - span) * (self._phase / 200.0)
            painter.drawRoundedRect(QRectF(track.left() + offset, track.top(), span, track.height()), 1.5, 1.5)
        else:
            value = max(0.0, min(1.0, float(self._progress)))
            painter.drawRoundedRect(
                QRectF(track.left(), track.top(), max(2.0, track.width() * value), track.height()), 1.5, 1.5
            )

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_colors()
            self.update()

    # ------------------------------------------------------------------
    # 内容更新（总线用）
    # ------------------------------------------------------------------
    def set_content(
        self,
        *,
        text: str | None = None,
        title: str | None = None,
        severity: str | ToastLevel | None = None,
        progress: float | None = _UNSET,  # type: ignore[assignment]
        detail: str | None = None,
        actions: tuple[ToastAction, ...] | None = None,
        closable: bool | None = None,
    ) -> bool:
        """更新内容；返回高度是否变化（变化时总线会重排）。"""
        before = self.height()
        if title is not None:
            self._title_label.setText(title)
            self._title_label.setVisible(bool(title))
        if text is not None:
            self._text_label.setText(text)
            self._text_label.setVisible(bool(text))
            self._expanded = False
            self._apply_text_clamp()
            self._update_more_label()
        if detail is not None:
            self._detail = detail
            self.setToolTip(detail)
            self._text_label.setToolTip(detail)
        if severity is not None:
            self._level, _ = normalize_level(severity)
            self._severity = _severity_for(self._level)
            self._apply_level_visuals()
            if self._needs_phase_timer() and not self._phase_timer.isActive():
                self._phase_timer.start()
            elif not self._needs_phase_timer():
                self._phase_timer.stop()
        if progress is not _UNSET:
            self._progress = progress  # type: ignore[assignment]
        if actions is not None:
            self._actions = tuple(actions)
            self._rebuild_actions()
        if closable is not None:
            self._closable = bool(closable)
            self._close_button.setVisible(self._closable)
        self.updateGeometry()
        self._fit_height()
        return abs(self.height() - before) > 1

    def set_life(self, life: int) -> None:
        """重设停留时长并重新计时；``0`` 表示常驻。"""
        self._life = max(0, int(life))
        self._timer.stop()
        if self._life > 0 and not self._closing:
            self._timer.start(self._life)

    # ------------------------------------------------------------------
    # 显示 / 消失
    # ------------------------------------------------------------------
    @classmethod
    def show_message(
        cls,
        parent: QWidget,
        text: str,
        title: str = "",
        severity: str = "info",
        life: int | None = None,
        offset_top: int = 0,
    ) -> CToast:
        """在 ``parent`` 右上角弹出一条通知（最新的排在最上面）。

        ``offset_top`` 用于避开标题栏等顶部区域。基座内部请优先走
        ``toast_bus()``；本方法保留给旧调用方与组件预览。
        """
        _, limit, _, _, _ = _settings()
        key = id(parent)
        if key not in cls._stacks:
            # 父窗口销毁时清掉分组，避免 id 复用后串栈
            parent.destroyed.connect(lambda *_: cls._stacks.pop(key, None))
        stack = cls._stacks.setdefault(key, [])
        while len(stack) >= limit:
            stack[-1].dismiss(ToastDismissReason.SUPERSEDED, immediate=True)

        toast = cls(parent, text, title, severity, life, offset_top)
        stack.insert(0, toast)
        cls._reflow(parent)
        toast.animate_in(toast.pos())
        return toast

    def animate_in(self, target: QPoint) -> None:
        """从右侧滑入并淡入到 ``target``。"""
        self._fit_height()
        self.show()
        self.raise_()
        start = QPoint(target.x() + 20, target.y())
        self.move(start)
        self._opacity.setOpacity(0.0)

        fade = QPropertyAnimation(self._opacity, b"opacity", self)
        fade.setDuration(self._duration)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.start()
        self._fade = fade

        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(self._duration)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.setStartValue(start)
        slide.setEndValue(target)
        slide.start()
        self._slide = slide

    @classmethod
    def clear(cls, parent: QWidget) -> None:
        for toast in list(cls._stacks.get(id(parent), [])):
            toast.dismiss(ToastDismissReason.CLEARED, immediate=True)

    def dismiss(
        self,
        reason: str | ToastDismissReason | bool = ToastDismissReason.MANUAL,
        immediate: bool = False,
    ) -> None:
        """关闭；``reason`` 会随 ``closed_reason`` 与 ``dismiss_reason()`` 回传。

        兼容旧写法 ``dismiss(True)``（等价于 ``immediate=True``）。
        """
        if isinstance(reason, bool):
            immediate, reason = reason, ToastDismissReason.MANUAL
        if self._closing:
            return
        self._closing = True
        self._dismiss_reason = ToastDismissReason(str(reason))
        self._timer.stop()
        self._phase_timer.stop()
        if immediate or self._duration <= 0 or not self.isVisible():
            self._finish()
            return
        fade = QPropertyAnimation(self._opacity, b"opacity", self)
        fade.setDuration(self._duration)
        fade.setStartValue(self._opacity.opacity())
        fade.setEndValue(0.0)
        fade.finished.connect(self._finish)
        fade.start()
        self._fade = fade
        self._finish_timer.start(self._duration)

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._finish_timer.stop()
        parent = self.parentWidget()
        if parent is not None:
            stack = self._stacks.get(id(parent), [])
            if self in stack:
                stack.remove(self)
            if not stack:
                self._stacks.pop(id(parent), None)
            else:
                self._reflow(parent)
        self.closed.emit()
        self.closed_reason.emit(str(self._dismiss_reason))
        self.hide()
        self.deleteLater()

    @classmethod
    def _reflow(cls, parent: QWidget) -> None:
        stack = cls._stacks.get(id(parent), [])
        _, _, _, margin, spacing = _settings()
        y = margin
        for toast in stack:
            y = max(y, margin + toast._offset_top)
            # 新通知插入时，旧通知的滑入动画终点已过期，先停掉再重新落位
            if toast._slide is not None and toast._slide.state() == QAbstractAnimation.State.Running:
                toast._slide.stop()
            toast.move(parent.width() - toast.width() - margin, y)
            y += toast.height() + spacing
            # 无显示环境下 show() 可能投递一次伪 enter 事件把倒计时停掉；
            # 重新落位时补一次启动，保证自动消失不会被悬停状态卡死。
            if toast._life > 0 and not toast._closing and not toast._timer.isActive():
                toast._timer.start(toast._life)

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self._reflow(watched)
        return super().eventFilter(watched, event)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._life > 0 and not self._closing:
            self._timer.start(self._life)
        super().leaveEvent(event)


__all__ = ["CToast"]
