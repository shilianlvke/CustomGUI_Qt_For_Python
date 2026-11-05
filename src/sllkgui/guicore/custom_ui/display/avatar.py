"""头像（复刻 PrimeVue Aura Avatar）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from .icon import tinted_pixmap
from .palette import tokens

_SIZES = {"sm": 32, "md": 40, "lg": 48, "xl": 64}


def _resolve_size(size: str | int) -> int:
    if isinstance(size, str):
        return _SIZES.get(size, 40)
    return max(16, int(size))


class CAvatar(QWidget):
    """圆形/方形头像：文字、图标或图片。"""

    def __init__(
        self,
        label: str = "",
        icon=None,
        image: str | None = None,
        shape: str = "circle",
        size: str | int = "md",
        parent=None,
    ):
        super().__init__(parent)
        self._label = label
        self._icon = icon
        self._pixmap = QPixmap(image) if image else QPixmap()
        self._shape = "square" if shape == "square" else "circle"
        self._size = _resolve_size(size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self._size, self._size)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def label(self) -> str:
        return self._label

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_image(self, image: str | None) -> None:
        self._pixmap = QPixmap(image) if image else QPixmap()
        self.update()

    def set_shape(self, shape: str) -> None:
        self._shape = "square" if shape == "square" else "circle"
        self.update()

    def set_size(self, size: str | int) -> None:
        self._size = _resolve_size(size)
        self.setFixedSize(self._size, self._size)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._size, self._size)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        if self._shape == "circle":
            path.addEllipse(rect)
        else:
            radius = max(4.0, rect.width() / 8)
            path.addRoundedRect(rect, radius, radius)
        return path

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        rect = QRectF(self.rect())
        path = self._path(rect)

        if not self._pixmap.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = self._pixmap.scaled(rect.size().toSize(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = rect.left() + (rect.width() - scaled.width()) / 2
            y = rect.top() + (rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
            painter.end()
            return

        painter.fillPath(path, QColor(palette["surface_strong"]))
        if self._icon is not None:
            icon_size = int(self._size * 0.45)
            pixmap = tinted_pixmap(self._icon, palette["muted"], icon_size, self.devicePixelRatioF())
            if pixmap is not None:
                logical = pixmap.deviceIndependentSize()
                painter.drawPixmap(
                    int((self.width() - logical.width()) / 2),
                    int((self.height() - logical.height()) / 2),
                    pixmap,
                )
        else:
            font = QFont(self.font())
            font.setPixelSize(max(11, int(self._size * 0.38)))
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(palette["text"]))
            painter.drawText(rect, Qt.AlignCenter, self._label)
        painter.end()


__all__ = ["CAvatar"]
