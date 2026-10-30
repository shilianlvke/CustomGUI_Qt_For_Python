"""可折叠面板（复刻 PrimeVue Aura Panel）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings

from ..paint_utils import draw_chevron
from .collapse import CollapseAnimator
from .style import panel_colors, paint_surface, with_alpha


class _ChevronButton(QAbstractButton):
    """24×24 的 chevron 按钮，按展开进度旋转。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)

    def set_progress(self, progress: float) -> None:
        progress = max(0.0, min(1.0, float(progress)))
        if abs(progress - self._progress) > 1e-3:
            self._progress = progress
            self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(panel_colors()["muted"])
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(180 * self._progress)
        draw_chevron(painter, QPointF(0, 0), color, size=8, direction="down", width=1.7)
        painter.end()


class _PanelHeader(QWidget):
    """标题区：标题 / 副标题 / 右侧扩展位 / chevron。"""

    toggled = Signal()

    def __init__(self, title: str, subtitle: str, toggleable: bool, parent=None):
        super().__init__(parent)
        self._toggleable = toggleable
        self._hover = False
        if toggleable:
            self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 12, 10)
        layout.setSpacing(8)

        text_box = QWidget(self)
        text_box.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(title, text_box)
        title_font = QFont(AppSettings.family)
        title_font.setPixelSize(15)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)

        self.subtitle_label = QLabel(subtitle, text_box)
        subtitle_font = QFont(AppSettings.family)
        subtitle_font.setPixelSize(12)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setVisible(bool(subtitle))

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        layout.addWidget(text_box, 1)

        self.widgets_layout = QHBoxLayout()
        self.widgets_layout.setContentsMargins(0, 0, 0, 0)
        self.widgets_layout.setSpacing(6)
        layout.addLayout(self.widgets_layout, 0)

        self.chevron = _ChevronButton(self) if toggleable else None
        if self.chevron is not None:
            self.chevron.clicked.connect(self.toggled)
            layout.addWidget(self.chevron, 0, Qt.AlignVCenter)

        self._apply_colors()

    def _apply_colors(self) -> None:
        colors = panel_colors()
        self.title_label.setStyleSheet(f"color: {colors['text']}; background: transparent;")
        self.subtitle_label.setStyleSheet(f"color: {colors['muted']}; background: transparent;")

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() == event.Type.StyleChange:
            self._apply_colors()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not (self._toggleable and self._hover):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(with_alpha(panel_colors()["text"], 12))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(4, 2, -4, -2), 6, 6)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._toggleable and event.button() == Qt.LeftButton:
            self.toggled.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _PanelFooter(QWidget):
    """底部栏（顶部分隔线）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 10, 16, 12)
        self._layout.setSpacing(8)
        self._layout.addStretch()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setPen(QPen(QColor(panel_colors()["divider"]), 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.end()

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


class CPanel(QWidget):
    """面板：标题、可折叠内容、可选底部栏。"""

    expandedChanged = Signal(bool)

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        toggleable: bool = False,
        collapsed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._expanded = not collapsed

        self.header = _PanelHeader(title, subtitle, toggleable, self)
        self.header.toggled.connect(self.toggle)

        self._wrapper = QWidget(self)
        self._wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QVBoxLayout(self._wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        body = QWidget(self._wrapper)
        body.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(body)
        self.content_layout.setContentsMargins(16, 4, 16, 14)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignTop)
        wrapper_layout.addWidget(body)

        self._footer: _PanelFooter | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self._wrapper)

        self._animator = CollapseAnimator(self._wrapper, self._expanded, self)
        self._animator.progressChanged.connect(self._on_progress)

    # ------------------------------------------------------------------
    def _on_progress(self, progress: float) -> None:
        if self.header.chevron is not None:
            self.header.chevron.set_progress(progress)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded and not self._animator.is_running():
            return
        self._expanded = expanded
        self._animator.set_expanded(expanded, animate)
        self.expandedChanged.emit(expanded)

    def toggle(self) -> None:
        if self.header.chevron is None:
            return
        self.set_expanded(not self._expanded)

    def set_title(self, title: str) -> None:
        self.header.title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self.header.subtitle_label.setText(subtitle)
        self.header.subtitle_label.setVisible(bool(subtitle))

    def add_header_widget(self, widget: QWidget) -> None:
        self.header.widgets_layout.addWidget(widget)

    def set_footer(self, widget: QWidget) -> None:
        if self._footer is None:
            self._footer = _PanelFooter(self._wrapper)
            self._wrapper.layout().addWidget(self._footer)
        self._footer.add_widget(widget)

    def footer(self) -> _PanelFooter | None:
        return self._footer

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(320, self.layout().sizeHint().height())

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


__all__ = ["CPanel"]
