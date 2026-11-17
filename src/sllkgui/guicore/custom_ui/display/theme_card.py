"""主题预览卡片：名称 + 副标题 + 四个调色块，点击即切换。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from sllkgui.appcore import AppSettings, AppThemes, ColorPalette, get_design_tokens

#: 卡片上展示的调色板键（侧栏 / 画布 / 强调 / 标题文字）
_PREVIEW_KEYS = ("custom_dark_one", "custom_bg_one", "custom_context_color", "custom_text_title")


class CThemeCard(QWidget):
    """可点击的主题卡片，选中态使用强调色描边 + 勾选角标。"""

    clicked = Signal(str)

    def __init__(self, theme_name: str, subtitle: str = "", parent=None, *, title: str = ""):
        super().__init__(parent)
        self._name = str(theme_name)
        self._title = str(title or theme_name.replace("_", " ").title())
        self._subtitle = str(subtitle)
        self._selected = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(self._name)

    # ------------------------------------------------------------------
    def name(self) -> str:
        return self._name

    def subtitle(self) -> str:
        return self._subtitle

    def set_subtitle(self, text: str) -> None:
        self._subtitle = str(text)
        self.update()

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        value = bool(selected)
        if value != self._selected:
            self._selected = value
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(220, 74)

    def _preview_colors(self) -> list[str]:
        config = AppThemes.get(self._name)
        data = getattr(config, "data", None)
        if data is None:
            return []
        colors: list[str] = []
        for key in _PREVIEW_KEYS:
            try:
                colors.append(str(getattr(data, key)))
            except AttributeError:
                continue
        return colors

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        tokens = get_design_tokens()
        colors = tokens.colors
        accent = QColor(colors.border_context)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, tokens.radius.control, tokens.radius.control)
        if self._selected:
            fill = QColor(accent)
            fill.setAlpha(28)
            painter.fillPath(path, fill)
            painter.setPen(QPen(accent, 1.5))
        else:
            surface = colors.surface_interactive_hover if self._hover else colors.surface_card
            painter.fillPath(path, QColor(surface))
            painter.setPen(QPen(QColor(colors.surface_interactive_pressed), 1))
        painter.drawPath(path)

        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors.text_active if self._selected else colors.text_primary))
        painter.drawText(
            QRectF(rect.left() + 11, rect.top() + 7, rect.width() - 34, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._title,
        )

        if self._subtitle:
            sub_font = QFont(AppSettings.family)
            sub_font.setPixelSize(10)
            painter.setFont(sub_font)
            painter.setPen(QColor(colors.text_muted))
            painter.drawText(
                QRectF(rect.left() + 11, rect.top() + 24, rect.width() - 22, 15),
                Qt.AlignLeft | Qt.AlignVCenter,
                self._subtitle,
            )

        left = rect.left() + 11
        width = max(8.0, (rect.width() - 22) / 4)
        for index, value in enumerate(self._preview_colors()[:4]):
            chip = QRectF(left + index * width, rect.top() + 44, width - 3, 20)
            chip_path = QPainterPath()
            chip_path.addRoundedRect(chip, tokens.radius.control, tokens.radius.control)
            painter.fillPath(chip_path, QColor(value))
            border = QColor(ColorPalette.custom_white)
            border.setAlpha(22)
            painter.setPen(QPen(border, 1))
            painter.drawPath(chip_path)

        if self._selected:
            mark = QRectF(rect.right() - 22, rect.top() + 8, 14, 14)
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(mark)
            painter.setPen(QPen(QColor(colors.text_on_accent), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(
                mark.left() + 4, mark.center().y(), mark.left() + 6.2, mark.bottom() - 4
            )
            painter.drawLine(
                mark.left() + 6.2, mark.bottom() - 4, mark.right() - 3.5, mark.top() + 4.5
            )
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
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._name)
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = ["CThemeCard"]
