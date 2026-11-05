"""跟随锚点的小型确认气泡（Windows Fluent Design Flyout）。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..button import CButton
from ..display.palette import tokens
from ..line_edit.overlay import POPOVER_INSET, CPopover


class CConfirmPopup(CPopover):
    """贴住控件弹出的“是 / 否”确认气泡。

    :meth:`show_at` 接受锚点控件，可在展示时同步更新文案；点击「是」或
    「否」分别发出 :attr:`accepted` / :attr:`rejected` 并自动收起。
    """

    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        message: str = "",
        accept_text: str = "Yes",
        reject_text: str = "No",
        width: int = 280,
        parent=None,
    ):
        super().__init__(parent, width=width)
        self._label = QLabel(message, self)
        self._label.setWordWrap(True)
        self._label.setFixedWidth(width - 2 * POPOVER_INSET)
        self._label.setStyleSheet(f"color: {tokens()['text']}; background: transparent;")
        self.content_layout().addWidget(self._label)

        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addStretch(1)
        self._reject_button = CButton(reject_text, severity="secondary", variant="outlined", size="sm")
        self._accept_button = CButton(accept_text, severity="primary", size="sm")
        row_layout.addWidget(self._reject_button)
        row_layout.addWidget(self._accept_button)
        self.content_layout().addWidget(row)

        self._reject_button.clicked.connect(self.reject)
        self._accept_button.clicked.connect(self.accept)

    # ------------------------------------------------------------------
    # 文案
    # ------------------------------------------------------------------
    def message(self) -> str:
        return self._label.text()

    def set_message(self, message: str) -> None:
        self._label.setText(message)

    def accept_button(self) -> CButton:
        return self._accept_button

    def reject_button(self) -> CButton:
        return self._reject_button

    # ------------------------------------------------------------------
    # 展示与结果
    # ------------------------------------------------------------------
    def show_at(
        self,
        anchor,
        message: str | None = None,
        accept_text: str | None = None,
        reject_text: str | None = None,
    ) -> None:
        """贴住 ``anchor`` 展开；可在展示时覆盖消息与按钮文案。"""
        if message is not None:
            self._label.setText(message)
        if accept_text is not None:
            self._accept_button.setText(accept_text)
        if reject_text is not None:
            self._reject_button.setText(reject_text)
        super().show_at(anchor)

    def accept(self) -> None:
        self.accepted.emit()
        self.hide()

    def reject(self) -> None:
        self.rejected.emit()
        self.hide()


__all__ = ["CConfirmPopup"]
