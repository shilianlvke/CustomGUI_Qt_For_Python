"""首页：最小可运行 Surface。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from sllkgui.plugin import GalleryContext


class HomePage(QWidget):
    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(ctx.text("home.title", "Hello SllkGUI")))
