"""对话框（复刻 PrimeVue Aura Dialog）。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..button import CButton
from ..close_button import CCloseButton
from ..display.palette import tokens
from ..scroll import CScrollArea
from .base import _OverlayBase

_SIZE_WIDTH = {"sm": 360, "md": 480, "lg": 640, "xl": 800}


class _BodyScroll(CScrollArea):
    """正文滚动区：不超高时按内容高度撑开，超高时由对话框封顶后内滚。"""

    def __init__(self, parent=None):
        super().__init__(parent, background="transparent")

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        content = self.widget()
        if content is None:
            return super().sizeHint()
        hint = content.sizeHint()
        return QSize(hint.width() + 6, hint.height() + 6)


class _DialogHeader(QWidget):
    """标题栏：标题 + 关闭按钮，可拖动对话框。"""

    def __init__(self, dialog: CDialog, title: str, closable: bool):
        super().__init__(dialog.card())
        self._dialog = dialog
        self._press_global: QPoint | None = None
        self._card_start = QPoint()
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(8)

        self.title_label = QLabel(title, self)
        font = QFont(self.font())
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"color: {tokens()['text']}; background: transparent;")
        layout.addWidget(self.title_label, 1)

        self.close_button: CCloseButton | None = None
        if closable:
            self.close_button = CCloseButton(QColor(tokens()["muted"]), parent=self)
            self.close_button.clicked.connect(dialog.reject)
            layout.addWidget(self.close_button, 0, Qt.AlignVCenter)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setPen(QColor(tokens()["border"]))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self._dialog.is_draggable():
            self._press_global = event.globalPosition().toPoint()
            self._card_start = self._dialog.card().pos()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._press_global is not None:
            delta = event.globalPosition().toPoint() - self._press_global
            self._dialog.move_card(self._card_start + delta)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._press_global = None


class _DialogFooter(QWidget):
    """底部按钮区，带顶部分隔线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 16)
        layout.setSpacing(8)
        layout.addStretch()
        self._layout = layout

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setPen(QColor(tokens()["border"]))
        painter.drawLine(0, 0, self.width(), 0)
        painter.end()

    def add_button(self, button: QWidget) -> None:
        self._layout.addWidget(button)


class CDialog(_OverlayBase):
    """模态对话框：标题、正文、底部按钮，支持拖动与遮罩点击关闭。"""

    def __init__(
        self,
        title: str = "",
        text: str = "",
        width: int | str = 480,
        accept_text: str = "",
        reject_text: str = "",
        closable: bool = True,
        dismissable_mask: bool = True,
        draggable: bool = True,
        parent=None,
    ):
        if isinstance(width, str):
            width = _SIZE_WIDTH.get(width, 480)
        self._width = max(240, int(width))
        self._draggable = draggable
        self._title = title
        self._text = text
        self._accept_text = accept_text
        self._reject_text = reject_text
        super().__init__(parent, modal=True, closable=closable, dismissable_mask=dismissable_mask)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_card(self) -> None:
        card = self.card()
        card.setRadius(10)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header: _DialogHeader | None = None
        if self._title or self._closable:
            self.header = _DialogHeader(self, self._title, self._closable)
            self.header.setStyleSheet("background: transparent;")
            layout.addWidget(self.header)

        body = QWidget(card)
        body.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(body)
        self.content_layout.setContentsMargins(20, 16, 20, 16)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setSpacing(10)

        scroller = _BodyScroll(card)
        scroller.setWidget(body)
        scroller.setWidgetResizable(True)
        layout.addWidget(scroller, 1)

        if self._text:
            self._ensure_text_label().setText(self._text)

        self.footer: _DialogFooter | None = None
        if self._accept_text or self._reject_text:
            self._ensure_footer()

    def _ensure_footer(self) -> _DialogFooter:
        if self.footer is None:
            self.footer = _DialogFooter(self.card())
            self.card().layout().addWidget(self.footer)
            if self._reject_text:
                reject = CButton(self._reject_text, severity="secondary", variant="outlined")
                reject.clicked.connect(self.reject)
                self.footer.add_button(reject)
            if self._accept_text:
                accept = CButton(self._accept_text, severity="primary")
                accept.clicked.connect(self.accept)
                self.footer.add_button(accept)
        return self.footer

    def set_header(self, title: str, closable: bool | None = None) -> None:
        if self.header is None:
            return
        self.header.title_label.setText(title)
        self.header.setVisible(bool(title))
        if closable is not None and self.header.close_button is not None:
            self.header.close_button.setVisible(closable)

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def _layout_card(self) -> QRect:
        card = self.card()
        layout = card.layout()
        layout.activate()
        card.setFixedWidth(self._width)
        height = layout.heightForWidth(self._width) if layout.hasHeightForWidth() else layout.sizeHint().height()
        if height <= 0:
            height = layout.sizeHint().height()
        height = max(120, min(height, max(160, self.height() - 80)))
        x = max(0, (self.width() - self._width) // 2)
        y = max(0, (self.height() - height) // 2)
        card.setGeometry(x, y, self._width, height)
        return card.geometry()

    def is_draggable(self) -> bool:
        return self._draggable

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._width, 240)

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------
    def set_title(self, title: str) -> None:
        self.set_header(title)

    def set_text(self, text: str) -> None:
        self._ensure_text_label().setText(text)

    def _ensure_text_label(self) -> QLabel:
        label = getattr(self, "_text_label", None)
        if label is None:
            label = QLabel(self.card())
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {tokens()['text']}; background: transparent;")
            self.content_layout.addWidget(label)
            self._text_label = label
        return label

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def add_footer_button(
        self,
        text: str,
        severity: str = "secondary",
        variant: str = "outlined",
        role: str = "reject",
    ):
        footer = self._ensure_footer()
        button = CButton(text, severity=severity, variant=variant)
        button.clicked.connect(self.accept if role == "accept" else self.reject)
        footer.add_button(button)
        return button


__all__ = ["CDialog"]
