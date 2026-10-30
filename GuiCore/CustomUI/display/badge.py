"""徽标（复刻 PrimeVue Aura Badge，支持独立与叠加两种用法）。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..button.severity import contrast_text, normalize_severity, severity_color

_HEIGHTS = {"sm": 16, "md": 20, "lg": 24}
_FONTS = {"sm": 10, "md": 11, "lg": 12}


class CBadge(QWidget):
    """数字/文字徽标；``dot=True`` 时退化为小圆点。"""

    def __init__(
        self,
        text: str = "",
        severity: str = "primary",
        size: str = "md",
        dot: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._severity = normalize_severity(severity)
        self._size = size if size in _HEIGHTS else "md"
        self._dot = dot
        self._anchor: QWidget | None = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = self.font()
        font.setPixelSize(_FONTS[self._size])
        self.setFont(font)
        self._sync_size()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self._sync_size()
        self.update()

    def severity(self) -> str:
        return self._severity.value

    def set_severity(self, severity: str) -> None:
        self._severity = normalize_severity(severity)
        self.update()

    def _sync_size(self) -> None:
        height = _HEIGHTS[self._size]
        if self._dot:
            side = height // 2
            self.setFixedSize(side, side)
            return
        metrics = QFontMetrics(self.font())
        width = max(height, metrics.horizontalAdvance(self._text) + 12)
        self.setFixedSize(width, height)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self.width(), self.height())

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        base = severity_color(self._severity)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.fillPath(path, base)
        if not self._dot:
            painter.setPen(contrast_text(base))
            painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()

    # ------------------------------------------------------------------
    # 叠加到控件右上角（PrimeVue 的 Badge Overlay）
    # ------------------------------------------------------------------
    @classmethod
    def attach(
        cls,
        target: QWidget,
        text: str = "",
        severity: str = "danger",
        size: str = "sm",
        dot: bool = False,
    ) -> CBadge:
        """把徽标挂到 ``target`` 右上角，目标尺寸变化时自动跟随。"""
        parent = target.parentWidget()
        badge = cls(text, severity, size, dot, parent=parent or target)
        badge._anchor = target
        target.installEventFilter(badge)
        if parent is not None:
            parent.installEventFilter(badge)
        badge._reposition()
        badge.show()
        badge.raise_()
        return badge

    def _reposition(self) -> None:
        target = self._anchor
        if target is None:
            return
        parent = self.parentWidget()
        if parent is target:
            # 没有更外层的容器时退回控件内部右上角，避免被父级裁掉
            self.move(max(0, target.width() - self.width()), 0)
            return
        origin = target.mapTo(parent, QPoint(0, 0))
        self.move(origin.x() + target.width() - self.width() // 2, origin.y() - self.height() // 2)

    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if event.type() in (QEvent.Resize, QEvent.Move, QEvent.Show) and watched in (
            self._anchor,
            self.parentWidget(),
        ):
            self._reposition()
            self.raise_()
        return super().eventFilter(watched, event)


__all__ = ["CBadge"]
