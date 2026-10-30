"""三段式工具栏（复刻 PrimeVue Aura Toolbar）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from .style import panel_colors, paint_surface


class CToolbar(QWidget):
    """左 / 中 / 右三段工具栏。"""

    def __init__(self, spacing: int = 8, padding: tuple[int, int, int, int] = (14, 10, 14, 10), parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(*padding)
        root.setSpacing(spacing)

        self.start_layout = QHBoxLayout()
        self.start_layout.setContentsMargins(0, 0, 0, 0)
        self.start_layout.setSpacing(spacing)

        self.center_layout = QHBoxLayout()
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(spacing)

        self.end_layout = QHBoxLayout()
        self.end_layout.setContentsMargins(0, 0, 0, 0)
        self.end_layout.setSpacing(spacing)

        root.addLayout(self.start_layout, 0)
        root.addStretch(1)
        root.addLayout(self.center_layout, 0)
        root.addStretch(1)
        root.addLayout(self.end_layout, 0)

    # ------------------------------------------------------------------
    def add_start(self, widget: QWidget) -> QWidget:
        self.start_layout.addWidget(widget, 0, Qt.AlignVCenter)
        return widget

    def add_center(self, widget: QWidget) -> QWidget:
        self.center_layout.addWidget(widget, 0, Qt.AlignVCenter)
        return widget

    def add_end(self, widget: QWidget) -> QWidget:
        self.end_layout.addWidget(widget, 0, Qt.AlignVCenter)
        return widget

    def set_spacing(self, spacing: int) -> None:
        for layout in (self.start_layout, self.center_layout, self.end_layout):
            layout.setSpacing(spacing)
        self.layout().setSpacing(spacing)

    def set_padding(self, padding: tuple[int, int, int, int]) -> None:
        self.layout().setContentsMargins(*padding)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        hint = self.layout().sizeHint()
        return QSize(max(240, hint.width()), hint.height())

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()
        paint_surface(
            painter,
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            background=colors["background"],
            border=colors["border"],
        )
        painter.end()


__all__ = ["CToolbar"]
