"""标签（复刻 PrimeVue Aura Tag）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from customgui.appcore import AppSettings

from ..button.severity import contrast_text, normalize_severity, severity_color
from .icon import tinted_pixmap

HEIGHT = 24
PADDING_X = 9
ICON_SIZE = 13
ICON_GAP = 5


def _tag_config() -> tuple[int, int, int, int]:
    """(高度, 左右内边距, 图标尺寸, 图标间距)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.display_components
        return int(cfg.tag_height), int(cfg.tag_padding_x), int(cfg.tag_icon_size), int(cfg.tag_icon_gap)
    except Exception:
        return HEIGHT, PADDING_X, ICON_SIZE, ICON_GAP


class CTag(QWidget):
    """实心语义标签，可选图标与胶囊圆角。"""

    def __init__(
        self,
        text: str = "",
        severity: str = "primary",
        rounded: bool = False,
        icon=None,
        parent=None,
    ):
        super().__init__(parent)
        self._height, self._padding_x, self._icon_size, self._icon_gap = _tag_config()
        self._text = text
        self._severity = normalize_severity(severity)
        self._rounded = rounded
        self._icon = icon
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        self.setFixedHeight(self._height)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def severity(self) -> str:
        return self._severity.value

    def set_severity(self, severity: str) -> None:
        self._severity = normalize_severity(severity)
        self.update()

    def set_rounded(self, rounded: bool) -> None:
        self._rounded = rounded
        self.update()

    def set_icon(self, icon) -> None:
        self._icon = icon
        self.updateGeometry()
        self.update()

    # ------------------------------------------------------------------
    # 尺寸与绘制
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = metrics.horizontalAdvance(self._text) + self._padding_x * 2
        if self._icon is not None:
            width += self._icon_size + self._icon_gap
        return QSize(width, self._height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self.sizeHint()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        base = severity_color(self._severity)
        text_color = contrast_text(base)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2 if self._rounded else 4
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, base)

        left = self._padding_x
        if self._icon is not None:
            pixmap = tinted_pixmap(self._icon, text_color, self._icon_size, self.devicePixelRatioF())
            if pixmap is not None:
                painter.drawPixmap(int(left), int((self.height() - self._icon_size) / 2), pixmap)
                left += self._icon_size + self._icon_gap

        painter.setPen(text_color)
        painter.drawText(
            QRectF(left, 0, self.width() - left - self._padding_x, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._text,
        )
        painter.end()


__all__ = ["CTag"]
