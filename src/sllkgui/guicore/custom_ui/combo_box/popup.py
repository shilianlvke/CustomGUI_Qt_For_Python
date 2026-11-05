"""下拉弹层：与原生 ``QComboBox`` 弹出层不同，不使用任何 Qt 原生 popup。

设计要点（这也是重写 ``CComboBox`` 的根本原因）：

1. **没有难看的黑角**——弹层是顶层窗口的半透明子控件，圆角底板全部
   ``QPainter`` 自绘，不依赖 ``QMenu`` / ``QAbstractItemView`` 的半透明
   hack（那种做法在深色主题下会露出窗口底色，形成黑角）。
2. **不会被裁剪**——父级是 top-level window 而不是页面容器，因此放在
   ``QScrollArea`` 里也不会被滚动区裁掉。
3. **不被样式表绑架**——列表项由 ``QListWidget`` 的局部样式控制，与全局
   QSS 的 ``QComboBox::drop-down`` 等子控件规则完全解耦。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QWidget

from ..line_edit.input_style import colors, radius
from ..menu.menu_list import menu_colors


class ComboChevron(QWidget):
    """自绘小箭头：不占用任何图标资源，主题切换自动重绘。"""

    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = False

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != bool(expanded):
            self._expanded = bool(expanded)
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = colors()
        pen = QPen(QColor(palette["icon"]))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        center = self.rect().center()
        half = 4.0
        offset = 2.5 if self._expanded else -2.5
        path = QPainterPath()
        path.moveTo(center.x() - half, center.y() + offset)
        path.lineTo(center.x(), center.y() - offset)
        path.lineTo(center.x() + half, center.y() + offset)
        painter.drawPath(path)
        painter.end()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ComboList(QListWidget):
    """弹层内的列表：接管按键，把「选择/取消」翻译成信号。"""

    choose = Signal(int)
    dismiss = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CComboBox_PopupList")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choose.emit(self.currentRow())
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.dismiss.emit()
            event.accept()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.dismiss.emit()
            event.ignore()
            return
        super().keyPressEvent(event)


class ComboPopup(QFrame):
    """圆角弹层底板：透明背景 + 自绘圆角 + 内嵌列表。"""

    MARGIN = 5
    ROW_HEIGHT = 30
    MIN_WIDTH = 160
    MAX_WIDTH = 460
    MAX_HEIGHT = 360

    def __init__(self, combo) -> None:
        # 关键：父级是顶层窗口，避免被页面/滚动区裁剪
        super().__init__(combo.window())
        self.combo = combo
        self.setObjectName("CComboBox_Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.list = ComboList(self)
        self.list.choose.connect(self._choose)
        self.list.dismiss.connect(self.close_popup)
        self.list.itemClicked.connect(lambda item: self._choose(self.list.row(item)))
        self.list.viewport().setAutoFillBackground(False)
        self.hide()

    # ------------------------------------------------------------------
    def _apply_style(self) -> None:
        palette = menu_colors()
        corner = radius()
        text = palette["text"]
        muted = palette["muted"]
        accent = QColor(palette["accent"])
        hover = f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 36)"
        selected = f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 76)"
        self.list.setStyleSheet(
            "QListWidget#CComboBox_PopupList {"
            " background: transparent; border: none; outline: none;"
            f" color: {text}; padding: 0px;"
            "}"
            "QListWidget#CComboBox_PopupList::item {"
            f" min-height: {self.ROW_HEIGHT - 6}px; padding: 3px 8px;"
            f" border-radius: {corner - 1}px;"
            "}"
            f"QListWidget#CComboBox_PopupList::item:hover {{ background: {hover}; }}"
            f"QListWidget#CComboBox_PopupList::item:selected {{"
            f" background: {selected}; color: {text};"
            "}"
            f"QListWidget#CComboBox_PopupList::item:disabled {{ color: {muted}; }}"
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 弹层覆盖在页面之上：必须使用菜单级高不透明度底色。
        # 旧实现沿用输入框的 30% 玻璃色，会让下层正文直接透出来。
        palette = menu_colors()
        rect = QRectF(self.rect()).adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.setBrush(QColor(palette["background"]))
        corner = radius()
        painter.drawRoundedRect(rect, corner, corner)
        painter.end()

    # ------------------------------------------------------------------
    def _choose(self, row: int) -> None:
        if row < 0:
            return
        self.combo.setCurrentIndex(row)
        self.combo.activated.emit(row)
        self.close_popup()

    def close_popup(self) -> None:
        if self.isVisible():
            self.hide()
        self.combo._after_popup_closed()  # noqa: SLF001 - 与宿主组件协作

    # ------------------------------------------------------------------
    def show_for(self, entries, current: int, width: int) -> None:
        self._apply_style()
        self.list.clear()
        for entry in entries:
            item = QListWidgetItem(entry.text)
            item.setData(Qt.ItemDataRole.UserRole, entry.data)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list.addItem(item)

        rows = min(max(len(entries), 1), self.combo.maxVisibleItems())
        width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, width))
        height = min(rows * self.ROW_HEIGHT + self.MARGIN * 2 + 4, self.MAX_HEIGHT)
        self.list.setGeometry(self.MARGIN, self.MARGIN, width - self.MARGIN * 2, height - self.MARGIN * 2)

        if 0 <= current < self.list.count():
            self.list.setCurrentRow(current)
            self.list.scrollToItem(self.list.currentItem())
        elif self.list.count():
            self.list.setCurrentRow(-1)
            self.list.scrollToTop()

        parent = self.parentWidget()
        if parent is None:
            return
        anchor = self.combo.mapTo(parent, QPoint(0, self.combo.height() + 2))
        x = max(4, min(anchor.x(), max(parent.width() - width - 4, 4)))
        y = anchor.y()
        if y + height > parent.height() - 4:
            above = self.combo.mapTo(parent, QPoint(0, -height - 2)).y()
            y = above if above >= 4 else max(4, parent.height() - height - 4)
        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.update()
        self.list.setFocus(Qt.FocusReason.PopupFocusReason)


__all__ = ["ComboChevron", "ComboList", "ComboPopup"]
