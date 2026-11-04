"""多列 MegaMenu 下拉菜单。

顶层项沿用菜单栏的悬停行为；下拉面板把子项按 ``columns`` 均匀分列，
列内仍使用自绘 ``CMenuList``。``orientation`` 控制顶层项横排或竖排。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from customgui.appcore import AppSettings, get_design_tokens

from .menu_item import MenuItem, as_menu_item
from .menu_list import CMenuList, menu_colors
from .menubar import _MenuBarBase

#: 面板内边距与列间距
MEGA_PADDING = 6
MEGA_SPACING = 4
#: 单列宽度
COLUMN_WIDTH = 180


def _mega_menu_config() -> tuple[int, int, int]:
    """(面板内边距, 列间距, 单列宽度)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.menus
        return int(cfg.mega_padding), int(cfg.mega_spacing), int(cfg.mega_column_width)
    except Exception:
        return MEGA_PADDING, MEGA_SPACING, COLUMN_WIDTH


class _MegaPanel(QWidget):
    """MegaMenu 的多列弹层面板。"""

    itemClicked = Signal(object)
    closed = Signal()

    def __init__(self, items, columns: int = 2, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("CMegaMenu_Popup")
        self._radius = get_design_tokens().radius.window
        self._padding, self._spacing, self._column_width = _mega_menu_config()
        self._columns = max(1, int(columns))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(self._padding, self._padding, self._padding, self._padding)
        layout.setSpacing(self._spacing)

        rows = self._flatten(items)
        chunk = max(1, -(-len(rows) // self._columns)) if rows else 1
        chunks = [rows[index : index + chunk] for index in range(0, len(rows), chunk)] or [[]]
        for entries in chunks[: self._columns]:
            column = CMenuList(entries, width=self._column_width, draw_surface=False, parent=self)
            column.itemClicked.connect(self._on_item_clicked)
            layout.addWidget(column, 0)

        self.adjustSize()

    def _flatten(self, items) -> list[MenuItem]:
        rows: list[MenuItem] = []
        for item in items:
            normalized = as_menu_item(item)
            if normalized.items:
                rows.append(MenuItem(label=normalized.label, icon=normalized.icon, disabled=True))
                rows.extend(self._flatten(normalized.items))
            else:
                rows.append(normalized)
        return rows

    def _on_item_clicked(self, item: MenuItem) -> None:
        self.itemClicked.emit(item)
        self.hide()

    def show_at_global(self, position: QPoint) -> None:
        self.adjustSize()
        self.move(position)
        self.show()
        self.raise_()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = menu_colors()
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(body, self._radius, self._radius)
        painter.fillPath(path, QColor(colors["background"]))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawPath(path)
        painter.end()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().hideEvent(event)
        self.closed.emit()


class CMegaMenu(_MenuBarBase):
    """多列下拉菜单。

    Args:
        items: 顶层菜单项；子项列表会被均匀拆成 ``columns`` 列。
        columns: 下拉面板的列数。
        orientation: ``"horizontal"`` 横排顶层项，``"vertical"`` 竖排顶层项。
    """

    def __init__(self, items=None, columns: int = 2, orientation: str = "horizontal", parent=None):
        self._columns = max(1, int(columns))
        super().__init__(items, orientation=orientation, parent=parent)
        self.setObjectName("CMegaMenu_Widget")

    def columns(self) -> int:
        return self._columns

    def set_columns(self, columns: int) -> None:
        value = max(1, int(columns))
        if value == self._columns:
            return
        self.close_menu()
        self._columns = value

    def _create_popup(self, item: MenuItem):
        return _MegaPanel(item.items, columns=self._columns, parent=self)


__all__ = ["CMegaMenu"]
