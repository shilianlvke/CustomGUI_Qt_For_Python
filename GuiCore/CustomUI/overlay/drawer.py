"""抽屉（复刻 PrimeVue Aura Drawer）。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..close_button import CCloseButton
from ..display.palette import tokens
from .base import _OverlayBase, overlay_settings

_POSITIONS = ("left", "right", "top", "bottom")
_GRIP_BAND = 6  # 边缘拖拽热区宽度（像素）
_MIN_DRAWER = 200  # 与构造参数的最小尺寸一致
_DRAWER_MARGIN = 80  # 拖宽后至少给窗口留出的空间


class _EdgeGrip(QWidget):
    """抽屉边缘的隐形拖拽条：悬停显示主色细线，拖动改变抽屉尺寸。"""

    def __init__(self, drawer: CDrawer):
        super().__init__(drawer.card())
        self._drawer = drawer
        self._press_global: QPoint | None = None
        self._start_size = 0
        self._vertical = drawer._position in ("left", "right")
        self.setCursor(Qt.SizeHorCursor if self._vertical else Qt.SizeVerCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self.underMouse():
            return
        painter = QPainter(self)
        color = QColor(tokens()["accent"])
        if self._vertical:
            painter.fillRect(self.width() // 2 - 1, 0, 2, self.height(), color)
        else:
            painter.fillRect(0, self.height() // 2 - 1, self.width(), 2, color)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            # 拖动优先：停掉进行中的滑入动画
            slide = getattr(self._drawer, "_slide", None)
            if slide is not None and slide.state() == QPropertyAnimation.State.Running:
                slide.stop()
            self._press_global = event.globalPosition().toPoint()
            self._start_size = self._drawer._size
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._press_global is None:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        self._drawer._resize_from_grip(self._start_size, delta)
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._press_global = None
        event.accept()


class CDrawer(_OverlayBase):
    """侧边抽屉：左/右/上/下四个方向滑入。"""

    def __init__(
        self,
        title: str = "",
        position: str = "right",
        size: int = 360,
        closable: bool = True,
        dismissable_mask: bool = True,
        parent=None,
    ):
        self._title = title
        self._position = position if position in _POSITIONS else "right"
        self._size = max(200, int(size))
        self._target_rect = QRect()
        super().__init__(parent, modal=True, closable=closable, dismissable_mask=dismissable_mask)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_card(self) -> None:
        card = self.card()
        card.setRadius(0)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header: QWidget | None = None
        if self._title or self._closable:
            self.header = QWidget(card)
            self.header.setStyleSheet("background: transparent;")
            self.header.setFixedHeight(52)
            bar = QHBoxLayout(self.header)
            bar.setContentsMargins(20, 0, 12, 0)
            bar.setSpacing(8)
            self.title_label = QLabel(self._title, self.header)
            font = QFont(self.font())
            font.setPixelSize(16)
            font.setWeight(QFont.Weight.DemiBold)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet(f"color: {tokens()['text']}; background: transparent;")
            bar.addWidget(self.title_label, 1)
            if self._closable:
                close = CCloseButton(QColor(tokens()["muted"]), parent=self.header)
                close.clicked.connect(self.reject)
                bar.addWidget(close, 0, Qt.AlignVCenter)
            layout.addWidget(self.header)

        body = QWidget(card)
        body.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(body)
        self.content_layout.setContentsMargins(20, 16, 20, 20)
        self.content_layout.setSpacing(10)
        layout.addWidget(body)
        layout.addStretch(1)

        self._grip = _EdgeGrip(self)

    def set_title(self, title: str) -> None:
        if self.header is not None:
            self.title_label.setText(title)
            self.header.setVisible(bool(title))

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _layout_card(self) -> QRect:
        card = self.card()
        width, height = self.width(), self.height()
        if self._position == "right":
            rect = QRect(width - self._size, 0, self._size, height)
        elif self._position == "left":
            rect = QRect(0, 0, self._size, height)
        elif self._position == "top":
            rect = QRect(0, 0, width, self._size)
        else:
            rect = QRect(0, height - self._size, width, self._size)
        self._target_rect = rect
        card.setGeometry(rect)
        self._place_grip()
        return rect

    def _place_grip(self) -> None:
        """把拖拽条贴到抽屉的可拉伸边缘。"""
        grip = getattr(self, "_grip", None)
        if grip is None:
            return
        card = self.card()
        if self._position == "left":
            grip.setGeometry(card.width() - _GRIP_BAND, 0, _GRIP_BAND, card.height())
        elif self._position == "right":
            grip.setGeometry(0, 0, _GRIP_BAND, card.height())
        elif self._position == "top":
            grip.setGeometry(0, card.height() - _GRIP_BAND, card.width(), _GRIP_BAND)
        else:
            grip.setGeometry(0, 0, card.width(), _GRIP_BAND)
        grip.setVisible(True)
        grip.raise_()

    def _resize_from_grip(self, start: int, delta: QPoint) -> None:
        """拖拽边缘时更新抽屉主轴尺寸（left/top 增大、right/bottom 反向）。"""
        if self._position == "left":
            new_size = start + delta.x()
        elif self._position == "right":
            new_size = start - delta.x()
        elif self._position == "top":
            new_size = start + delta.y()
        else:
            new_size = start - delta.y()
        axis = self.width() if self._position in ("left", "right") else self.height()
        limit = max(_MIN_DRAWER, axis - _DRAWER_MARGIN)
        self._size = max(_MIN_DRAWER, min(int(new_size), limit))
        self._layout_card()

    def _offscreen_rect(self) -> QRect:
        target = self._target_rect
        if self._position == "right":
            return target.translated(self.width(), 0)
        if self._position == "left":
            return target.translated(-self.width(), 0)
        if self._position == "top":
            return target.translated(0, -self.height())
        return target.translated(0, self.height())

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        super().open_dialog()
        # 窗口此时完全透明，先把卡片挪到屏外再滑入，不会闪到最终位置
        self.card().setGeometry(self._offscreen_rect())
        slide = QPropertyAnimation(self.card(), b"geometry", self)
        slide.setDuration(overlay_settings()[1])
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.setStartValue(self._offscreen_rect())
        slide.setEndValue(self._target_rect)
        slide.start()
        self._slide = slide

    def _animate_out(self) -> None:
        duration = overlay_settings()[1]
        if duration <= 0 or not self.isVisible():
            self._finalize()
            return

        group = QParallelAnimationGroup(self)
        slide = QPropertyAnimation(self.card(), b"geometry", group)
        slide.setDuration(duration)
        slide.setEasingCurve(QEasingCurve.InCubic)
        slide.setStartValue(self.card().geometry())
        slide.setEndValue(self._offscreen_rect())
        group.addAnimation(slide)

        fade = QPropertyAnimation(self, b"windowOpacity", group)
        fade.setDuration(duration)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        group.addAnimation(fade)

        group.finished.connect(self._finalize)
        group.start()
        self._slide = slide

    def sizeHint(self):  # noqa: N802 - 覆写 Qt 命名

        return QSize(self._size, self._size)


__all__ = ["CDrawer"]
