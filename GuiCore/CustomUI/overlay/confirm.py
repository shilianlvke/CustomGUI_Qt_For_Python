"""确认对话框（复刻 PrimeVue Aura ConfirmDialog）。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..button.severity import normalize_severity
from ..display.palette import tokens
from ..feedback.message import _MessageIcon
from .dialog import CDialog


class CConfirmDialog(CDialog):
    """带语义图标的确认框，默认「Yes / No」。"""

    def __init__(
        self,
        title: str = "Confirm",
        message: str = "",
        severity: str = "warn",
        accept_text: str = "Yes",
        reject_text: str = "No",
        parent=None,
    ):
        super().__init__(
            title=title,
            width=420,
            accept_text=accept_text,
            reject_text=reject_text,
            parent=parent,
        )
        self._severity = normalize_severity(severity)

        row = QWidget(self.card())
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(14)
        layout.addWidget(_MessageIcon(self._severity, size=36, parent=row), 0)
        self.message_label = QLabel(message, row)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"color: {tokens()['text']}; background: transparent;")
        layout.addWidget(self.message_label, 1)
        self.content_layout.addWidget(row)

    @classmethod
    def ask(
        cls,
        parent,
        title: str = "Confirm",
        message: str = "",
        severity: str = "warn",
        accept_text: str = "Yes",
        reject_text: str = "No",
    ) -> bool:
        """阻塞式确认，返回是否点了确认。"""
        dialog = cls(title, message, severity, accept_text, reject_text, parent=parent)
        return dialog.exec_dialog()


__all__ = ["CConfirmDialog"]
