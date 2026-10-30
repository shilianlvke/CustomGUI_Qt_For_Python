"""手风琴（复刻 PrimeVue Aura Accordion）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from AppCore import AppSettings

from ..icon_utils import render_icon
from ..paint_utils import draw_chevron
from .collapse import CollapseAnimator
from .style import panel_colors, paint_surface, with_alpha

_HEADER_HEIGHT = 44


class _AccordionHeader(QWidget):
    """面板标题行：图标 + 标题 + 右侧 chevron（随展开进度旋转）。"""

    clicked = Signal()

    def __init__(self, title: str, icon: str | QIcon | None, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._progress = 0.0
        self._hover = False
        self._icon_cache: dict[tuple, object] = {}

        self.setFixedHeight(_HEADER_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        font = QFont(AppSettings.family)
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)

    def set_title(self, title: str) -> None:
        self._title = title
        self.update()

    def set_icon(self, icon: str | QIcon | None) -> None:
        self._icon = icon
        self.update()

    def set_progress(self, progress: float) -> None:
        progress = max(0.0, min(1.0, float(progress)))
        if abs(progress - self._progress) > 1e-3:
            self._progress = progress
            self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()

        if self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(colors["text"], 14))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(6, 3, -6, -3), 6, 6)

        left = 16.0
        if self._icon is not None:
            pixmap = render_icon(self._icon, QColor(colors["muted"]), 16, self.devicePixelRatioF())
            if pixmap is not None:
                painter.drawPixmap(int(left), int(self.height() / 2 - 8), pixmap)
            left += 24

        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(left, 0, max(0.0, self.width() - left - 46), self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._title,
        )

        center = QPointF(self.width() - 22, self.height() / 2)
        painter.save()
        painter.translate(center)
        painter.rotate(180 * self._progress)
        draw_chevron(painter, QPointF(0, 0), QColor(colors["muted"]), size=8, direction="down", width=1.7)
        painter.restore()
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
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CAccordionPanel(QWidget):
    """单个手风琴面板。"""

    expandedChanged = Signal(bool)

    def __init__(
        self,
        title: str = "",
        content: QWidget | None = None,
        icon: str | QIcon | None = None,
        expanded: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._expanded = bool(expanded)
        self._last = False

        self.header = _AccordionHeader(title, icon, self)
        self.header.clicked.connect(self.toggle)

        self._wrapper = QWidget(self)
        self._wrapper.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self._wrapper)
        self.content_layout.setContentsMargins(16, 4, 16, 14)
        self.content_layout.setSpacing(8)
        if content is not None:
            self.content_layout.addWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self._wrapper)

        self._animator = CollapseAnimator(self._wrapper, self._expanded, self)
        self._animator.progressChanged.connect(self.header.set_progress)

    # ------------------------------------------------------------------
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
        self.set_expanded(not self._expanded)

    def set_title(self, title: str) -> None:
        self.header.set_title(title)

    def set_icon(self, icon: str | QIcon | None) -> None:
        self.header.set_icon(icon)

    def set_last(self, last: bool) -> None:
        self._last = last
        self.update()

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._last:
            return
        painter = QPainter(self)
        colors = panel_colors()
        painter.setPen(QPen(QColor(colors["divider"]), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()


class CAccordion(QWidget):
    """手风琴容器：单开 / 多开。"""

    panelToggled = Signal(int, bool)

    def __init__(self, multiple: bool = False, parent=None):
        super().__init__(parent)
        self._panels: list[CAccordionPanel] = []
        self._multiple = multiple
        self._syncing = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignTop)

    # ------------------------------------------------------------------
    def add_panel(
        self,
        title: str,
        content: QWidget | None = None,
        icon: str | QIcon | None = None,
        expanded: bool = False,
    ) -> CAccordionPanel:
        panel = CAccordionPanel(title, content, icon, expanded=expanded, parent=self)
        index = len(self._panels)
        self._panels.append(panel)
        self._layout.addWidget(panel)
        panel.expandedChanged.connect(lambda value, i=index: self._on_panel_toggled(i, value))
        self._update_separators()
        return panel

    def panel(self, index: int) -> CAccordionPanel | None:
        return self._panels[index] if 0 <= index < len(self._panels) else None

    def count(self) -> int:
        return len(self._panels)

    def set_multiple(self, multiple: bool) -> None:
        self._multiple = multiple

    def active_index(self) -> int:
        for index, panel in enumerate(self._panels):
            if panel.is_expanded():
                return index
        return -1

    def set_active(self, index: int) -> None:
        if not (0 <= index < len(self._panels)):
            return
        self._syncing = True
        for position, panel in enumerate(self._panels):
            panel.set_expanded(position == index)
        self._syncing = False

    def expand_all(self) -> None:
        if not self._multiple:
            return
        for panel in self._panels:
            panel.set_expanded(True)

    def collapse_all(self) -> None:
        for panel in self._panels:
            panel.set_expanded(False)

    # ------------------------------------------------------------------
    def _on_panel_toggled(self, index: int, expanded: bool) -> None:
        if self._syncing:
            return
        if expanded and not self._multiple:
            self._syncing = True
            for position, panel in enumerate(self._panels):
                if position != index and panel.is_expanded():
                    panel.set_expanded(False)
            self._syncing = False
        self.panelToggled.emit(index, expanded)

    def _update_separators(self) -> None:
        for position, panel in enumerate(self._panels):
            panel.set_last(position == len(self._panels) - 1)

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


__all__ = ["CAccordion", "CAccordionPanel"]
