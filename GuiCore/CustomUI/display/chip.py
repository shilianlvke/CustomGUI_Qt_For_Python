"""标签片（复刻 PrimeVue Aura Chip）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from .icon import tinted_pixmap
from .palette import tokens
from ..paint_utils import draw_cross

HEIGHT = 28
PADDING_X = 10
ICON_SIZE = 14
ICON_GAP = 6


class CChip(QWidget):
    """胶囊标签片：图标 / 头像 / 可删除。"""

    removed = Signal()

    def __init__(
        self,
        text: str = "",
        icon=None,
        image: str | None = None,
        removable: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._image = QPixmap(image) if image else QPixmap()
        self._removable = removable
        self._hover_remove = False
        self._remove_rect = QRectF()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        self.setFixedHeight(HEIGHT)
        if removable:
            self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def set_removable(self, removable: bool) -> None:
        self._removable = removable
        self.setMouseTracking(removable)
        self.updateGeometry()
        self.update()

    def _leading_width(self) -> int:
        if not self._image.isNull():
            return 20
        if self._icon is not None:
            return ICON_SIZE
        return 0

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = PADDING_X * 2 + metrics.horizontalAdvance(self._text)
        leading = self._leading_width()
        if leading:
            width += leading + ICON_GAP
        if self._removable:
            width += 18
        return QSize(width, HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self.sizeHint()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.fillPath(path, QColor(palette["surface"]))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(palette["border"]))
        painter.drawPath(path)

        left = PADDING_X
        if not self._image.isNull():
            avatar = QRectF(left, (self.height() - 20) / 2, 20, 20)
            clip = QPainterPath()
            clip.addEllipse(avatar)
            painter.save()
            painter.setClipPath(clip)
            scaled = self._image.scaled(20, 20, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(int(avatar.left()), int(avatar.top()), scaled)
            painter.restore()
            left += 20 + ICON_GAP
        elif self._icon is not None:
            pixmap = tinted_pixmap(self._icon, palette["muted"], ICON_SIZE)
            if pixmap is not None:
                painter.drawPixmap(int(left), int((self.height() - ICON_SIZE) / 2), pixmap)
                left += ICON_SIZE + ICON_GAP

        right = self.width() - PADDING_X - (18 if self._removable else 0)
        painter.setPen(QColor(palette["text"]))
        painter.drawText(
            QRectF(left, 0, right - left, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._text,
        )

        if self._removable:
            self._remove_rect = QRectF(self.width() - PADDING_X - 14, (self.height() - 16) / 2, 16, 16)
            if self._hover_remove:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(palette["surface_strong"]))
                painter.drawEllipse(self._remove_rect)
            draw_cross(painter, self._remove_rect.adjusted(3, 3, -3, -3), palette["muted"], 1.4)
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._removable:
            return
        hover = self._remove_rect.contains(event.position())
        if hover != self._hover_remove:
            self._hover_remove = hover
            self.setCursor(Qt.PointingHandCursor if hover else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover_remove = False
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._removable and event.button() == Qt.LeftButton and self._remove_rect.contains(event.position()):
            self.removed.emit()
            event.accept()


__all__ = ["CChip"]
