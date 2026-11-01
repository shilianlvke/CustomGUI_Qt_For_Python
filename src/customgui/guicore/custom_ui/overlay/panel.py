"""跟随锚点的浮层（复刻 PrimeVue Aura OverlayPanel）。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ..line_edit.overlay import CPopover


class COverlayPanel(CPopover):
    """点击控件后在下方展开的浮层；再次点击/点外部自动关闭。"""

    toggled = Signal(bool)

    def __init__(self, target: QWidget, width: int = 300):
        super().__init__(target, width=width)
        self._target = target
        self._open = False

    def target(self) -> QWidget:
        return self._target

    def is_open(self) -> bool:
        return self._open

    def set_content(self, widget: QWidget) -> None:
        self.content_layout().addWidget(widget)

    def open_panel(self) -> None:
        if self._open:
            return
        self._open = True
        self.show_at(self._target)
        self.toggled.emit(True)

    def close_panel(self) -> None:
        if self._open:
            self.hide()

    def toggle(self) -> None:
        if self._open:
            self.close_panel()
        else:
            self.open_panel()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        was_open = self._open
        self._open = False
        super().hideEvent(event)
        if was_open:
            self.toggled.emit(False)


__all__ = ["COverlayPanel"]
