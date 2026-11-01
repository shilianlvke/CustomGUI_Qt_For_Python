"""``CComboBox``：自绘下拉选择框（不继承 ``QComboBox``）。

为什么不继承原生控件
--------------------
``QComboBox`` 的弹出层是 Qt 内部的顶层瞬态子窗口，圆角只能靠
``QAbstractItemView`` 的半透明 hack 实现——深色主题下会露出窗口底色
（也就是"边缘始终有不好看的角"），而且在 ``QScrollArea`` 里会被裁剪。
本实现改为「透明子控件 + 自绘圆角底板」，见 :mod:`popup`。

另外原生控件在获得焦点时鼠标滚轮会**静默改变选中项**（滚动页面时最容易
误触），这里 ``wheelEvent`` 一律 ``ignore()``，把滚动交还给父级。

样式约定
--------
颜色与状态由 ``customgui.guicore/styles.py`` 的 ``#CComboBox_Field`` 提供；
本类只做几何与交互。``focused`` / ``hovered`` 动态属性驱动描边。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QFontMetrics, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from ....appcore import get_theme_manager
from ..line_edit.input_style import colors, field_font
from .model import EntryList
from .popup import ComboChevron, ComboPopup

#: ``QComboBox.InsertPolicy`` 的兼容常量（本实现不自动插入，保留以兼容调用点）
_NO_INSERT = 0


class CComboBox(QWidget):
    """自绘下拉选择框，API 对齐 ``QComboBox`` 的常用子集。

    >>> combo = CComboBox(items=["简体中文", "English"])
    >>> combo.currentText()
    '简体中文'
    >>> combo.currentIndexChanged.connect(print)
    """

    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)
    activated = Signal(int)
    textActivated = Signal(str)

    NoInsert = _NO_INSERT

    def __init__(
        self,
        items: list | None = None,
        placeholder_text: str = "",
        is_editable: bool = False,
        size: str = "md",
        max_visible_items: int = 10,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = EntryList()
        self._placeholder = placeholder_text or ""
        self._editable = False
        self._max_visible = max(1, int(max_visible_items))
        self._popup: ComboPopup | None = None
        self._window: QWidget | None = None
        self._app_filter = False
        self._size_name = size

        self.setObjectName("CComboBox_Field")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("focused", False)
        self.setProperty("hovered", False)
        self.setFont(field_font(size))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(96)
        self.setFixedHeight(max(28, QFontMetrics(self.font()).height() + 12))

        self._chevron = ComboChevron(self)
        self._chevron.clicked.connect(self._toggle_popup)
        self._place_chevron()

        if items:
            self.addItems(items)
        if is_editable:
            self.setEditable(True)
        self._sync_tooltip()

        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        widest = max((metrics.horizontalAdvance(text) for text in self._model.texts()), default=0)
        widest = max(widest, metrics.horizontalAdvance(self._placeholder))
        chrome = self._text_left() + self._chevron.width() + 16
        return QSize(max(120, widest + chrome), self.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(96, self.height())

    def resizeEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._place_chevron()

    def _place_chevron(self) -> None:
        right = self.rect().right() - 8
        self._chevron.move(right - self._chevron.width() + 1, (self.height() - self._chevron.height()) // 2)

    def _text_left(self) -> int:
        return 10

    def _text_rect(self) -> QRectF:
        left = self._text_left()
        right = self.width() - self._chevron.width() - 10
        return QRectF(left, 0, max(0, right - left), self.height())

    # ------------------------------------------------------------------
    # 数据 API（对齐 QComboBox）
    # ------------------------------------------------------------------
    def addItem(self, text: str, userData: Any = None) -> None:  # noqa: N802 - 对齐 Qt 命名
        if self._model.add(text, userData):
            self._after_current_changed(emit_index=False)
        self.updateGeometry()

    def addItems(self, texts) -> None:  # noqa: N802 - 对齐 Qt 命名
        for text in texts:
            self._model.add(text)
        self._after_current_changed(emit_index=False)
        self.updateGeometry()

    def insertItem(self, index: int, text: str, userData: Any = None) -> None:  # noqa: N802
        self._model.insert(index, text, userData)
        self._after_current_changed(emit_index=False)
        self.updateGeometry()

    def insertItems(self, index: int, texts) -> None:  # noqa: N802 - 对齐 Qt 命名
        position = max(0, int(index))
        for offset, text in enumerate(texts):
            self._model.insert(position + offset, text)
        self._after_current_changed(emit_index=False)
        self.updateGeometry()

    def removeItem(self, index: int) -> None:  # noqa: N802 - 对齐 Qt 命名
        if self._model.remove(index):
            self._after_current_changed(emit_index=True)
        self.updateGeometry()

    def clear(self) -> None:  # noqa: D401 - 对齐 Qt 命名
        self._close_popup()
        if self._model.clear():
            self._after_current_changed(emit_index=True)
        self.updateGeometry()

    def setItemData(self, index: int, value: Any, role: int = Qt.ItemDataRole.UserRole) -> None:  # noqa: N802
        if 0 <= index < len(self._model):
            self._model[index].data = value

    def count(self) -> int:
        return len(self._model)

    def itemText(self, index: int) -> str:  # noqa: N802 - 对齐 Qt 命名
        return self._model[index].text if 0 <= index < len(self._model) else ""

    def itemData(self, index: int, role: int = Qt.ItemDataRole.UserRole):  # noqa: N802
        return self._model[index].data if 0 <= index < len(self._model) else None

    def setItemText(self, index: int, text: str) -> None:  # noqa: N802 - 对齐 Qt 命名
        if 0 <= index < len(self._model):
            self._model[index].text = str(text)
            if index == self._model.index:
                self.currentTextChanged.emit(self.currentText())
            self.updateGeometry()
            self.update()

    def currentIndex(self) -> int:  # noqa: N802 - 对齐 Qt 命名
        return self._model.index

    def currentText(self) -> str:  # noqa: N802 - 对齐 Qt 命名
        entry = self._model.current
        return entry.text if entry is not None else ""

    def currentData(self):  # noqa: N802 - 对齐 Qt 命名
        entry = self._model.current
        return entry.data if entry is not None else None

    def findText(self, text: str) -> int:  # noqa: N802 - 对齐 Qt 命名
        return self._model.find_text(str(text))

    def findData(self, data: Any) -> int:  # noqa: N802 - 对齐 Qt 命名
        return self._model.find_data(data)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - 对齐 Qt 命名
        if self._model.set_index(index):
            self._after_current_changed(emit_index=True)

    def setCurrentText(self, text: str) -> None:  # noqa: N802 - 对齐 Qt 命名
        position = self._model.find_text(str(text))
        if position >= 0:
            self.setCurrentIndex(position)
            return
        if self._editable and self._model.set_index(-1):
            self.currentIndexChanged.emit(-1)
            self.currentTextChanged.emit(str(text))

    def setEditable(self, editable: bool) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._editable = bool(editable)
        self.setCursor(Qt.CursorShape.IBeamCursor if self._editable else Qt.CursorShape.PointingHandCursor)

    def isEditable(self) -> bool:  # noqa: N802 - 对齐 Qt 命名
        return self._editable

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._placeholder = str(text or "")
        self._sync_tooltip()
        self.updateGeometry()
        self.update()

    def placeholderText(self) -> str:  # noqa: N802 - 对齐 Qt 命名
        return self._placeholder

    def setInsertPolicy(self, policy: int) -> None:  # noqa: N802 - 对齐 Qt 命名
        """兼容占位：本实现不自动把用户输入写入选项。"""
        del policy

    def setMaxVisibleItems(self, count: int) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._max_visible = max(1, int(count))

    def maxVisibleItems(self) -> int:  # noqa: N802 - 对齐 Qt 命名
        return self._max_visible

    # ------------------------------------------------------------------
    # 状态同步
    # ------------------------------------------------------------------
    def _after_current_changed(self, *, emit_index: bool) -> None:
        self._sync_tooltip()
        if emit_index:
            self.currentIndexChanged.emit(self._model.index)
        self.currentTextChanged.emit(self.currentText())
        self.update()

    def _sync_tooltip(self) -> None:
        self.setToolTip(self.currentText() or self._placeholder)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = colors()

        # 底色与描边走 QSS（#CComboBox_Field），这里只画文本 / 占位符
        text = self.currentText()
        muted = not text
        painter.setPen(QColor(palette["placeholder"] if muted else palette["text"]))
        painter.setFont(self.font())
        rect = self._text_rect()
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text or self._placeholder,
        )
        painter.end()

    def _theme_changed(self) -> None:
        self._chevron.update()
        if self._popup is not None and self._popup.isVisible():
            self._popup._apply_style()  # noqa: SLF001 - 弹层由本类持有
        self.update()

    def _set_state(self, name: str, value: bool) -> None:
        if bool(self.property(name)) == bool(value):
            return
        self.setProperty(name, bool(value))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ------------------------------------------------------------------
    # 弹层
    # ------------------------------------------------------------------
    def showPopup(self) -> None:  # noqa: N802 - 对齐 Qt 命名
        if not len(self._model) or not self.isEnabled():
            return
        if self._popup is None:
            self._popup = ComboPopup(self)
            self.destroyed.connect(self._popup.deleteLater)
        parent = self.window()
        if self._popup.parentWidget() is not parent:
            self._popup.setParent(parent)
        if self._popup.isVisible():
            self._close_popup()
            return

        self.setFocus(Qt.FocusReason.PopupFocusReason)
        metrics = QFontMetrics(self.font())
        widest = max((metrics.horizontalAdvance(text) for text in self._model.texts()), default=0)
        width = max(self.width(), widest + 44)
        self._popup.show_for(self._model.entries(), self._model.index, width)
        self._chevron.set_expanded(True)

        self._window = parent
        parent.installEventFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_filter = True

    def hidePopup(self) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._close_popup()

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._close_popup()
        elif self.isEnabled() and len(self._model):
            self.showPopup()

    def _close_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
        self._after_popup_closed()

    def _after_popup_closed(self) -> None:
        if self._app_filter:
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._app_filter = False
        if self._window is not None:
            try:
                self._window.removeEventFilter(self)
            except RuntimeError:
                pass
            self._window = None
        self._chevron.set_expanded(False)

    @staticmethod
    def _global_rect(widget: QWidget) -> QRectF:
        top_left = widget.mapToGlobal(QPoint(0, 0))
        return QRectF(top_left.x(), top_left.y(), widget.width(), widget.height())

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - 覆写 Qt 命名
        if self._popup is not None and self._popup.isVisible():
            kind = event.type()
            if kind == QEvent.Type.MouseButtonPress:
                position = getattr(event, "globalPosition", None)
                if position is None:
                    return super().eventFilter(watched, event)
                point = position()
                if not self._global_rect(self._popup).contains(point) and not self._global_rect(self).contains(point):
                    self._close_popup()
            elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._close_popup()
                return True
            elif watched is self._window and kind in (
                QEvent.Type.Resize,
                QEvent.Type.Move,
                QEvent.Type.WindowStateChange,
                QEvent.Type.Hide,
            ):
                self._close_popup()
        return super().eventFilter(watched, event)

    def wheelEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        """滚动页面时**绝不**改变选中项——这是原生 QComboBox 的老问题。"""
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - 覆写 Qt 命名
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            if self._popup is not None and self._popup.isVisible():
                self._popup.list.keyPressEvent(event)
            else:
                step = 1 if key == Qt.Key.Key_Down else -1
                self.setCurrentIndex(max(0, min(len(self._model) - 1, self._model.index + step)))
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._toggle_popup()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self._close_popup()
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self.setCurrentIndex(0)
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self.setCurrentIndex(len(self._model) - 1)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._toggle_popup()
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._set_state("hovered", True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._set_state("hovered", False)
        super().leaveEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._set_state("focused", True)
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 - 覆写 Qt 命名
        if self._popup is None or not self._popup.isVisible():
            self._set_state("focused", False)
        super().focusOutEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._close_popup()
        super().hideEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self._close_popup()
        super().changeEvent(event)


__all__ = ["CComboBox"]
