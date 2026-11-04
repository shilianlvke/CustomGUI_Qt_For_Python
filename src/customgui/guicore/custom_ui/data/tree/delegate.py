"""树行委托：``CTree`` 的单列绘制与 ``CTreeTable`` 的多列绘制。

两者共用 ``paint.py`` 的行内布局算法，差别只在「列」的概念：
``CTree`` 只有第一列（整行自绘），``CTreeTable`` 的其余列复用
:class:`~..table.CTableColumn` 的文本 / 语义标签回调。
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ...button.severity import contrast_text, normalize_severity, severity_color
from ...display.palette import tokens
from ...paint_utils import draw_chevron
from ..table import CTableColumn
from .paint import (
    ROW_HEIGHT,
    _check_state,
    _paint_checkbox,
    _paint_icon,
    _paint_row_background,
    _row_metrics,
)
from .roles import NODE_ROLE


class _CTreeDelegate(QStyledItemDelegate):
    """CTree 行绘制：箭头、复选框、图标与文字。"""

    def __init__(self, checkbox: bool, parent=None):
        super().__init__(parent)
        self._checkbox = checkbox

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        _paint_row_background(painter, option)

        rect = QRectF(option.rect)
        arrow, box, icon_x, text_x = _row_metrics(rect, index, self._checkbox)
        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        text_color = QColor(colors["text" if enabled else "muted"])

        if arrow is not None:
            view = option.widget
            expanded = view.isExpanded(index) if view is not None and hasattr(view, "isExpanded") else False
            draw_chevron(
                painter,
                arrow.center(),
                colors["muted"],
                size=9,
                direction="up" if expanded else "down",
            )

        if box is not None:
            _paint_checkbox(painter, box, _check_state(index.data(Qt.ItemDataRole.CheckStateRole)))

        _paint_icon(
            painter,
            index,
            icon_x,
            rect.center().y(),
            text_color,
            option.widget.devicePixelRatioF() if option.widget is not None else 1.0,
        )

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        available = max(0.0, rect.right() - 10 - text_x)
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(available))
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(text_x, rect.top(), available, rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            elided,
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), ROW_HEIGHT))


class _TreeTableDelegate(QStyledItemDelegate):
    """CTreeTable 单元格绘制：第一列画树形结构，其余列复用语义标签。"""

    def __init__(self, columns: list[CTableColumn], checkbox: bool, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._checkbox = checkbox

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        _paint_row_background(painter, styled)
        if index.column() == 0:
            self._paint_tree_cell(painter, styled, index)
        else:
            self._paint_content_cell(painter, styled, index)
        painter.restore()

    def _paint_tree_cell(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        rect = QRectF(option.rect)
        arrow, box, icon_x, text_x = _row_metrics(rect, index, self._checkbox)
        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        text_color = QColor(colors["text" if enabled else "muted"])

        if arrow is not None:
            view = option.widget
            expanded = view.isExpanded(index) if view is not None and hasattr(view, "isExpanded") else False
            draw_chevron(painter, arrow.center(), colors["muted"], size=9, direction="up" if expanded else "down")
        if box is not None:
            _paint_checkbox(painter, box, _check_state(index.data(Qt.ItemDataRole.CheckStateRole)))
        _paint_icon(
            painter,
            index,
            icon_x,
            rect.center().y(),
            text_color,
            option.widget.devicePixelRatioF() if option.widget is not None else 1.0,
        )

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        available = max(0.0, rect.right() - 10 - text_x)
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(available))
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(text_x, rect.top(), available, rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            elided,
        )

    def _paint_content_cell(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if not (0 <= index.column() < len(self._columns)):
            return
        column = self._columns[index.column()]
        node = index.data(NODE_ROLE)
        if not isinstance(node, dict):
            node = {}
        value = node.get(column.field)
        tag = column.tag_for(value, node)
        if tag is not None:
            self._paint_tag(painter, option, index, tag)
            return

        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        painter.setPen(QPen(QColor(colors["text" if enabled else "muted"])))
        rect = QRectF(option.rect).adjusted(10, 0, -10, 0)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(max(0, rect.width())))
        painter.drawText(rect, option.displayAlignment, elided)

    @staticmethod
    def _paint_tag(
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        tag: tuple[str, str],
    ) -> None:
        severity, text = tag
        base = severity_color(normalize_severity(severity))
        font = QFont(option.font)
        font.setPixelSize(max(10, font.pixelSize() - 2))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = max(24, metrics.horizontalAdvance(text) + 16)
        height = 22
        rect = QRectF(option.rect)
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

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 38))


__all__ = ["_CTreeDelegate", "_TreeTableDelegate"]
