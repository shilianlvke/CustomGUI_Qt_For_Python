"""内联消息（Windows Fluent Design InfoBar 风格）。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import ColorPalette

from ..button.severity import Severity, contrast_text, normalize_severity, severity_color
from ..close_button import CCloseButton as _CloseButton
from ..display.palette import is_dark_theme
from ..paint_utils import draw_check

#: 消息条图标尺寸（配置不可用时的兜底默认）
_ICON_SIZE = 20


def message_palette(severity) -> dict[str, QColor]:
    """消息卡片配色：浅色主题用低饱和底，深色主题用主色 15% 叠加。"""
    sev = normalize_severity(severity)
    dark = is_dark_theme()
    if sev is Severity.CONTRAST:
        # Fluent 的反相卡片：深色主题浅底、浅色主题深底，颜色取主题而不是固定灰阶
        if dark:
            return {
                "background": QColor(ColorPalette.custom_text_title),
                "border": QColor(ColorPalette.custom_text_title),
                "text": QColor(ColorPalette.custom_bg_one),
                "title": QColor(ColorPalette.custom_bg_one),
                "accent": QColor(ColorPalette.custom_bg_one),
                "outlined": QColor(ColorPalette.custom_dark_two),
            }
        return {
            "background": QColor(ColorPalette.custom_text_title),
            "border": QColor(ColorPalette.custom_text_title),
            "text": QColor(ColorPalette.custom_white),
            "title": QColor(ColorPalette.custom_white),
            "accent": QColor(ColorPalette.custom_white),
            "outlined": QColor(ColorPalette.custom_dark_three),
        }
    if sev is Severity.SECONDARY:
        return {
            "background": QColor(ColorPalette.custom_bg_one if dark else ColorPalette.custom_dark_two),
            "border": QColor(ColorPalette.custom_bg_two if dark else ColorPalette.custom_dark_four),
            "text": QColor(ColorPalette.custom_text_title if dark else ColorPalette.custom_text_foreground),
            "title": QColor(ColorPalette.custom_text_active if dark else ColorPalette.custom_text_title),
            "accent": QColor(ColorPalette.custom_icon_color if dark else ColorPalette.custom_text_description),
            "outlined": QColor(ColorPalette.custom_text_title if dark else ColorPalette.custom_text_foreground),
        }

    base = severity_color(sev)
    background = QColor(base)
    background.setAlpha(38 if dark else 30)
    border = QColor(base)
    border.setAlpha(96 if dark else 76)
    return {
        "background": background,
        "border": border,
        "text": QColor(ColorPalette.custom_text_foreground),
        "title": QColor(ColorPalette.custom_text_title),
        "accent": base,
        "outlined": base,
    }


class _MessageIcon(QWidget):
    """圆形语义图标：i / ! / ✓ / × / ?。"""

    def __init__(self, severity, size: int | None = None, parent=None):
        super().__init__(parent)
        # 图标尺寸来自 settings（实例初始化时读取，避免导入期触发配置加载）
        if size is None:
            try:
                from sllkgui.appcore import AppSettings

                size = int(AppSettings.feedback.message_icon_size)
            except Exception:
                size = _ICON_SIZE
        self._severity = normalize_severity(severity)
        self._size = max(12, int(size))
        self.setFixedSize(self._size, self._size)

    def set_severity(self, severity) -> None:
        self._severity = normalize_severity(severity)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = message_palette(self._severity)
        accent = colors["accent"]
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(self.rect()))
        painter.setPen(contrast_text(accent))

        size = self._size
        if self._severity is Severity.SUCCESS:
            inset = size * 0.2
            draw_check(painter, QRectF(inset, inset, size - inset * 2, size - inset * 2), contrast_text(accent), 1.8)
        elif self._severity is Severity.DANGER:
            pen = QPen(contrast_text(accent), 1.8, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(size * 0.3, size * 0.3, size * 0.7, size * 0.7)
            painter.drawLine(size * 0.7, size * 0.3, size * 0.3, size * 0.7)
        else:
            glyph = "!" if self._severity is Severity.WARN else ("?" if self._severity is Severity.HELP else "i")
            font = QFont(self.font())
            font.setPixelSize(max(9, int(size * 0.65)))
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, glyph)
        painter.end()


class CMessage(QFrame):
    """内联提示条：severity + 标题 + 正文 + 可关闭。"""

    closed = Signal()

    def __init__(
        self,
        text: str = "",
        title: str = "",
        severity: str = "info",
        closable: bool = False,
        show_icon: bool = True,
        outlined: bool = False,
        simple: bool = False,
        close_on_click: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._severity = normalize_severity(severity)
        self._outlined = outlined
        self._simple = simple
        self._close_on_click = close_on_click
        self._applying = False

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        if simple:
            layout.setContentsMargins(4, 4, 4, 4)
        else:
            layout.setContentsMargins(14, 11, 12, 11)
        layout.setSpacing(10)

        self._icon = _MessageIcon(self._severity, parent=self) if show_icon else None
        if self._icon is not None:
            layout.addWidget(self._icon, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = QLabel(title, self)
        title_font = QFont(self.font())
        title_font.setPixelSize(14)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setVisible(bool(title))
        text_layout.addWidget(self._title_label)

        self._text_label = QLabel(text, self)
        text_font = QFont(self.font())
        text_font.setPixelSize(13)
        self._text_label.setFont(text_font)
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._text_label.setVisible(bool(text))
        text_layout.addWidget(self._text_label)

        layout.addLayout(text_layout, 1)

        self._close_button = _CloseButton(QColor(ColorPalette.custom_white), parent=self) if closable else None
        if self._close_button is not None:
            self._close_button.clicked.connect(self._on_close_clicked)
            layout.addWidget(self._close_button, 0, Qt.AlignTop)

        self._apply_colors()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._text_label.text()

    def set_text(self, text: str) -> None:
        self._text_label.setText(text)
        self._text_label.setVisible(bool(text))

    def title(self) -> str:
        return self._title_label.text()

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)
        self._title_label.setVisible(bool(title))

    def severity(self) -> str:
        return self._severity.value

    def set_severity(self, severity: str) -> None:
        self._severity = normalize_severity(severity)
        if self._icon is not None:
            self._icon.set_severity(self._severity)
        self._apply_colors()
        self.update()

    def is_closable(self) -> bool:
        return self._close_button is not None

    def set_closable(self, closable: bool) -> None:
        if closable and self._close_button is None:
            self._close_button = _CloseButton(QColor(ColorPalette.custom_white), parent=self)
            self._close_button.clicked.connect(self._on_close_clicked)
            self.layout().addWidget(self._close_button, 0, Qt.AlignTop)
            self._apply_colors()
        elif not closable and self._close_button is not None:
            self._close_button.deleteLater()
            self._close_button = None

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def _apply_colors(self) -> None:
        if self._applying or not hasattr(self, "_title_label"):
            return
        self._applying = True
        colors = message_palette(self._severity)
        base = colors["outlined"] if self._outlined else colors["text"]
        title = colors["outlined"] if self._outlined else colors["title"]
        if self._simple:
            accent = colors["accent"]
            base = accent.lighter(135) if is_dark_theme() else accent.darker(150)
            title = accent.lighter(155) if is_dark_theme() else accent.darker(170)
        self._text_label.setStyleSheet(f"color: {base.name()}; background: transparent;")
        self._title_label.setStyleSheet(f"color: {title.name()}; background: transparent;")
        if self._close_button is not None:
            self._close_button.set_color(base)
        self._applying = False

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_colors()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._simple:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = message_palette(self._severity)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        if not self._outlined:
            painter.fillPath(path, colors["background"])
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(colors["border"], 1))
            painter.drawPath(path)
        else:
            painter.fillPath(path, QColor(ColorPalette.custom_transparent))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(colors["border"], 1))
            painter.drawPath(path)
        painter.end()

    def _on_close_clicked(self) -> None:
        self.closed.emit()
        if self._close_on_click:
            self.hide()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        hint = super().sizeHint()
        return QSize(max(hint.width(), 240), hint.height())


__all__ = ["CMessage", "message_palette"]
