"""单元格绘制 ``CTableDelegate``：分组头、语义标签、普通文本。"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ...button.severity import contrast_text, normalize_severity, severity_color
from ...display.palette import tokens
from .roles import GROUP_ROLE, TAG_ROLE


class CTableDelegate(QStyledItemDelegate):
    """单元格绘制：分组头、语义标签、普通文本。"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        if index.data(GROUP_ROLE):
            self._paint_group(painter, option, index)
            return
        tag = index.data(TAG_ROLE)
        if tag:
            self._paint_tag(painter, option, index, tag)
            return
        super().paint(painter, option, index)

    @staticmethod
    def _paint_group(painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        colors = tokens()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect)
        painter.fillRect(rect, QColor(colors["surface"]))
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors["muted"]))
        text = str(index.data(Qt.DisplayRole) or "")
        text = painter.fontMetrics().elidedText(text, Qt.ElideRight, max(0, int(rect.width()) - 24))
        painter.drawText(rect.adjusted(12, 0, -12, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    @staticmethod
    def _paint_tag(painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex, tag) -> None:
        # 先让样式系统画选中/悬停底色（文字置空）
        styled = QStyleOptionViewItem(option)
        styled.text = ""
        widget = styled.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        severity, text = tag
        base = severity_color(normalize_severity(severity))
        font = QFont(option.font)
        font.setPixelSize(max(10, font.pixelSize() - 2))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        rect = QRectF(option.rect)
        max_width = max(24, int(rect.width()) - 20)
        text = metrics.elidedText(text, Qt.ElideRight, max(0, max_width - 16))
        width = min(max_width, max(24, metrics.horizontalAdvance(text) + 16))
        height = 22
        x = rect.left() + 10
        if option.displayAlignment & Qt.AlignRight:
            x = rect.right() - width - 10
        elif option.displayAlignment & Qt.AlignHCenter:
            x = rect.center().x() - width / 2
        y = rect.center().y() - height / 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, width, height), height / 2, height / 2)
        painter.fillPath(path, base)
        painter.setPen(contrast_text(base))
        painter.drawText(QRectF(x, y, width, height), Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 40))


__all__ = ["CTableDelegate"]
