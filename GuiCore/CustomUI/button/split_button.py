"""分体按钮：主按钮 + 分隔线 + 下拉箭头（对应 Sakai 的 SplitButton）。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QWidget

from AppCore import PathFactory

from .button import CButton, _SIZES


class CSplitButton(QWidget):
    """主操作 + 附加菜单的分体按钮。

    主按钮负责默认动作，右侧箭头按钮弹出 ``items`` 指定的菜单项；
    两段共用同一 severity 与尺寸，中间由 1px 分隔线衔接。
    """

    clicked = Signal()
    actionTriggered = Signal(str)

    def __init__(
        self,
        text: str = "Save",
        items: list[tuple[str, str | None]] | None = None,
        severity: str = "primary",
        size: str = "md",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CSplitButton_Widget")
        self._size = size if size in _SIZES else "md"
        self._items = list(items or [])
        self._menu = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        height = _SIZES[self._size].height
        self._main = CButton(
            text=text,
            severity=severity,
            size=self._size,
            corners=(True, False, False, True),
            parent=self,
        )
        self._arrow = CButton(
            icon="icon_arrow_down",
            severity=severity,
            size=self._size,
            fixed_width=height,
            border_visible=False,
            corners=(False, True, True, False),
            parent=self,
        )
        self._arrow.set_divider(True)

        layout.addWidget(self._main)
        layout.addWidget(self._arrow)
        self.setFixedHeight(height)

        self._main.clicked.connect(self.clicked.emit)
        self._arrow.clicked.connect(self._show_menu)

    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._main.text()

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._main.setText(text)
        self.updateGeometry()

    def main_button(self) -> CButton:
        return self._main

    def arrow_button(self) -> CButton:
        return self._arrow

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        main = self._main.sizeHint()
        return QSize(main.width() + _SIZES[self._size].height, main.height())

    def _show_menu(self) -> None:
        if not self._items:
            return
        from ..menu import CMenu

        menu = CMenu(self, width=150)
        for label, icon in self._items:
            action = menu.addAction(QIcon(PathFactory.set_svg_icon(icon)) if icon else QIcon(), label)
            action.triggered.connect(lambda _checked=False, name=label: self.actionTriggered.emit(name))
        self._menu = menu
        menu.popup(self._arrow.mapToGlobal(QPoint(0, self._arrow.height() + 2)))


__all__ = ["CSplitButton"]
