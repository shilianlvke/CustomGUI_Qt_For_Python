"""表单栅格（复刻 Sakai / PrimeVue FormLayout）。

一个字段容器 ``CFormField`` + 一个栅格容器 ``CFormGrid``，覆盖
Vertical / Vertical Grid / Horizontal / Inline / Help Text / Advanced 六种布局。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from AppCore import AppSettings, ColorPalette

from .style import panel_colors


class _FieldLabel(QWidget):
    """标签 + 必填星号。"""

    def __init__(self, text: str, required: bool = False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.label = QLabel(text, self)
        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        self.label.setFont(font)

        self.star = QLabel("*", self)
        self.star.setFont(font)
        self.star.setVisible(required)

        layout.addWidget(self.label, 0, Qt.AlignVCenter)
        layout.addWidget(self.star, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        self._apply_colors()

    def _apply_colors(self) -> None:
        colors = panel_colors()
        self.label.setStyleSheet(f"color: {colors['text']}; background: transparent;")
        self.star.setStyleSheet(f"color: {ColorPalette.custom_red}; background: transparent;")

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def set_required(self, required: bool) -> None:
        self.star.setVisible(required)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() == event.Type.StyleChange:
            self._apply_colors()


class CFormField(QWidget):
    """单个表单项：标签、控件、帮助文本。"""

    def __init__(
        self,
        label: str = "",
        field: QWidget | None = None,
        help_text: str = "",
        required: bool = False,
        label_position: str = "top",
        label_width: int = 96,
        parent=None,
    ):
        super().__init__(parent)
        self._label_position = label_position if label_position in ("top", "left", "inline", "none") else "top"
        self._label_width = max(40, int(label_width))
        self._field = field
        self._required = required
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.label_row: _FieldLabel | None = None
        if self._label_position != "none":
            self.label_row = _FieldLabel(label, required, self)

        self.help_label = QLabel(help_text, self)
        help_font = QFont(AppSettings.family)
        help_font.setPixelSize(12)
        self.help_label.setFont(help_font)
        self.help_label.setWordWrap(True)
        self.help_label.setVisible(bool(help_text))

        self._build_layout()
        if field is not None:
            self._place_field(field)

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        position = self._label_position
        if position == "left":
            self._layout = QGridLayout(self)
            self._layout.setContentsMargins(0, 0, 0, 0)
            self._layout.setHorizontalSpacing(12)
            self._layout.setVerticalSpacing(4)
            self.label_row.setFixedWidth(self._label_width)
            self._layout.addWidget(self.label_row, 0, 0, Qt.AlignLeft | Qt.AlignTop)
            self._layout.setColumnStretch(1, 1)
            return

        if position == "inline":
            self._layout = QHBoxLayout(self)
            self._layout.setContentsMargins(0, 0, 0, 0)
            self._layout.setSpacing(8)
            self._layout.addWidget(self.label_row, 0, Qt.AlignVCenter)
            return

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        if self.label_row is not None:
            self._layout.addWidget(self.label_row)
        if position == "top":
            return

    def _place_field(self, field: QWidget) -> None:
        if isinstance(self._layout, QGridLayout):
            self._layout.addWidget(field, 0, 1)
            self._layout.addWidget(self.help_label, 1, 1)
            return
        if isinstance(self._layout, QHBoxLayout):
            self._layout.addWidget(field, 1)
            self.help_label.hide()
            return
        self._layout.addWidget(field)
        self._layout.addWidget(self.help_label)

    # ------------------------------------------------------------------
    def field(self) -> QWidget | None:
        return self._field

    def set_field(self, field: QWidget) -> None:
        old = self._field
        if old is not None:
            old.setParent(None)
            old.deleteLater()
        self._field = field
        self._place_field(field)

    def set_label(self, text: str) -> None:
        if self.label_row is not None:
            self.label_row.set_text(text)

    def set_required(self, required: bool) -> None:
        self._required = required
        if self.label_row is not None:
            self.label_row.set_required(required)

    def set_help_text(self, text: str) -> None:
        self.help_label.setText(text)
        self.help_label.setVisible(bool(text) and not isinstance(self._layout, QHBoxLayout))


class CFormGrid(QWidget):
    """表单栅格：按 ``columns`` 自动换行，支持跨列。"""

    def __init__(
        self,
        label_position: str = "top",
        columns: int = 1,
        label_width: int = 96,
        spacing: int = 12,
        parent=None,
    ):
        super().__init__(parent)
        self._label_position = label_position
        self._label_width = label_width
        self._columns = max(1, int(columns))
        self._row = 0
        self._col = 0

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(spacing)
        self._layout.setVerticalSpacing(spacing)
        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1)

    # ------------------------------------------------------------------
    def add_field(
        self,
        label: str,
        field: QWidget,
        help_text: str = "",
        required: bool = False,
        span: int = 1,
    ) -> CFormField:
        span = max(1, min(int(span), self._columns))
        item = CFormField(
            label,
            field,
            help_text=help_text,
            required=required,
            label_position=self._label_position,
            label_width=self._label_width,
            parent=self,
        )
        self._place(item, span)
        return item

    def add_widget(self, widget: QWidget, span: int | None = None) -> QWidget:
        """整行控件（如 Textarea、按钮行）。"""
        span = self._columns if span is None else max(1, min(int(span), self._columns))
        self._place(widget, span)
        return widget

    def add_row(self, fields: list[tuple]) -> list[CFormField]:
        """一行多个字段：``[(label, widget[, help_text[, required]]), ...]``。"""
        created = []
        for entry in fields:
            label, widget = entry[0], entry[1]
            help_text = entry[2] if len(entry) > 2 else ""
            required = entry[3] if len(entry) > 3 else False
            created.append(self.add_field(label, widget, help_text=help_text, required=required))
        return created

    def add_section(self, title: str) -> QLabel:
        label = QLabel(title, self)
        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        label.setFont(font)
        self._place(label, self._columns)
        label.setStyleSheet(f"color: {panel_colors()['text']}; background: transparent;")
        return label

    def count(self) -> int:
        return self._layout.count()

    def set_columns(self, columns: int) -> None:
        self._columns = max(1, int(columns))

    # ------------------------------------------------------------------
    def _place(self, widget: QWidget, span: int) -> None:
        if self._col + span > self._columns:
            self._row += 1
            self._col = 0
        self._layout.addWidget(widget, self._row, self._col, 1, span)
        self._col += span
        if self._col >= self._columns:
            self._row += 1
            self._col = 0


__all__ = ["CFormField", "CFormGrid"]
