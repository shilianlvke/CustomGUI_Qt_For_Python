"""导航补充件：面包屑与步骤条。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from AppCore import AppSettings

from ..icon_utils import render_icon
from ..paint_utils import draw_check, draw_chevron
from .style import panel_colors


class CBreadcrumb(QWidget):
    """面包屑：图标 + 文本 + 分隔箭头。"""

    itemClicked = Signal(int)

    def __init__(self, items: list | None = None, separator: str = "chevron", parent=None):
        super().__init__(parent)
        self._items: list[dict] = []
        self._separator = separator
        self._hover = -1
        self._rects: list[QRectF] = []
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        self.setFont(font)
        if items:
            self.set_items(items)

    # ------------------------------------------------------------------
    def set_items(self, items: list) -> None:
        self._items = [self._normalize(item) for item in items]
        self.update()

    def add_item(self, label: str, icon: str | None = None, command=None) -> None:
        self._items.append({"label": label, "icon": icon, "command": command})
        self.update()

    def items(self) -> list[dict]:
        return list(self._items)

    def _normalize(self, item) -> dict:
        if isinstance(item, dict):
            return {
                "label": str(item.get("label", "")),
                "icon": item.get("icon"),
                "command": item.get("command"),
            }
        return {"label": str(item), "icon": None, "command": None}

    # ------------------------------------------------------------------
    def _separator_width(self) -> int:
        return 14 if self._separator == "chevron" else 12

    def _item_width(self, item: dict, metrics: QFontMetrics) -> int:
        width = metrics.horizontalAdvance(item["label"]) + 8
        if item["icon"] is not None:
            width += 20
        return width

    def _measure(self) -> None:
        metrics = QFontMetrics(self.font())
        rects: list[QRectF] = []
        x = 0.0
        for item in self._items:
            width = float(self._item_width(item, metrics))
            rects.append(QRectF(x, 0, width, self.height()))
            x += width + self._separator_width()
        self._rects = rects

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()
        metrics = QFontMetrics(self.font())
        self._measure()
        dpr = self.devicePixelRatioF()

        for index, (item, rect) in enumerate(zip(self._items, self._rects)):
            last = index == len(self._items) - 1
            if last:
                color = QColor(colors["text"])
            elif index == self._hover:
                color = QColor(colors["accent"])
            else:
                color = QColor(colors["muted"])

            text_x = rect.left() + 4
            if item["icon"] is not None:
                pixmap = render_icon(item["icon"], color, 14, dpr)
                if pixmap is not None:
                    painter.drawPixmap(int(text_x), int(rect.center().y() - 7), pixmap)
                text_x += 20

            available = max(0.0, rect.right() - text_x - 4)
            text = metrics.elidedText(item["label"], Qt.ElideRight, int(available))
            painter.setPen(color)
            painter.drawText(
                QRectF(text_x, 0, available, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                text,
            )

            if not last:
                center = QPointF(rect.right() + self._separator_width() / 2, rect.center().y())
                if self._separator == "chevron":
                    draw_chevron(painter, center, QColor(colors["track"]), size=6, direction="right", width=1.4)
                else:
                    painter.setPen(QPen(QColor(colors["track"]), 1))
                    painter.drawText(
                        QRectF(center.x() - 6, 0, 12, self.height()),
                        Qt.AlignCenter,
                        str(self._separator)[:1],
                    )
        painter.end()

    def _index_at(self, position) -> int:
        for index, rect in enumerate(self._rects):
            if rect.contains(position):
                return index
        return -1

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.position())
            if index >= 0:
                item = self._items[index]
                self.itemClicked.emit(index)
                if callable(item["command"]):
                    item["command"]()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            clickable = 0 <= index < len(self._items) - 1
            self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = sum(self._item_width(item, metrics) + self._separator_width() for item in self._items)
        return QSize(max(160, width), 32)


class CSteps(QWidget):
    """步骤条：序号圆点 + 标签 + 连接线。"""

    stepClicked = Signal(int)

    def __init__(self, steps: list[str] | None = None, active: int = 0, clickable: bool = True, parent=None):
        super().__init__(parent)
        self._steps: list[str] = list(steps or [])
        self._active = max(0, int(active))
        self._clickable = clickable
        self._hover = -1
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        self.setFont(font)

    # ------------------------------------------------------------------
    def set_steps(self, steps: list[str], active: int | None = None) -> None:
        self._steps = list(steps)
        if active is not None:
            self._active = max(0, min(int(active), max(0, len(self._steps) - 1)))
        self.update()

    def set_active(self, index: int) -> None:
        if not self._steps:
            return
        self._active = max(0, min(int(index), len(self._steps) - 1))
        self.update()

    def active(self) -> int:
        return self._active

    def steps(self) -> list[str]:
        return list(self._steps)

    # ------------------------------------------------------------------
    def _block_width(self) -> float:
        if not self._steps:
            return 0.0
        return self.width() / len(self._steps)

    def _circle_rect(self, index: int) -> QRectF:
        block = self._block_width()
        diameter = 26.0
        x = block * index + 2
        return QRectF(x, (self.height() - diameter) / 2, diameter, diameter)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._steps:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()
        block = self._block_width()
        metrics = QFontMetrics(self.font())

        number_font = QFont(self.font())
        number_font.setPixelSize(12)
        number_font.setWeight(QFont.Weight.DemiBold)

        for index, label in enumerate(self._steps):
            circle = self._circle_rect(index)
            completed = index < self._active
            active = index == self._active
            highlight = index == self._hover and self._clickable

            if index < len(self._steps) - 1:
                start = QPointF(circle.right(), circle.center().y())
                end = QPointF(block * (index + 1) + 2, circle.center().y())
                painter.setPen(QPen(QColor(colors["accent"] if completed else colors["track"]), 2))
                painter.drawLine(start, end)

            painter.setPen(Qt.NoPen)
            if completed or active:
                painter.setBrush(QColor(colors["accent"]))
            else:
                painter.setBrush(QColor(colors["background"]))
            painter.drawEllipse(circle)
            if not completed and not active:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(colors["accent"] if highlight else colors["track"]), 1.2))
                painter.drawEllipse(circle.adjusted(0.5, 0.5, -0.5, -0.5))

            if completed:
                draw_check(painter, circle.adjusted(7, 7, -7, -7), QColor(colors["on_accent"]), 2.0)
            else:
                painter.setFont(number_font)
                painter.setPen(QColor(colors["on_accent"] if active else colors["muted"]))
                painter.drawText(circle, Qt.AlignCenter, str(index + 1))

            text_left = circle.right() + 8
            text_width = max(0.0, block - (text_left - block * index) - 8)
            if active:
                text_color = colors["text"]
            elif completed:
                text_color = colors["text"]
            else:
                text_color = colors["muted"]
            if highlight:
                text_color = colors["accent"]
            painter.setFont(self.font())
            painter.setPen(QColor(text_color))
            painter.drawText(
                QRectF(text_left, 0, text_width, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(label, Qt.ElideRight, int(text_width)),
            )
        painter.end()

    def _index_at(self, position) -> int:
        if not self._steps or self._block_width() <= 0:
            return -1
        index = int(position.x() // self._block_width())
        return max(0, min(index, len(self._steps) - 1))

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self._clickable:
            index = self._index_at(event.position())
            if index >= 0:
                self.stepClicked.emit(index)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._clickable:
            super().mouseMoveEvent(event)
            return
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.setCursor(Qt.PointingHandCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(max(240, 120 * len(self._steps)), 52)


__all__ = ["CBreadcrumb", "CSteps"]
