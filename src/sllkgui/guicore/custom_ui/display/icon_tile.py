"""图标方块：强调色淡底 + 单色图标或自带图片。

用于插件卡片、详情页、设置页等"一个产品/模块的标识"。缓存用
``lru_cache(maxsize=64)`` 而不是无上限字典：插件数量增长时不会单调吃内存，
换主题/换图标后仍可按 (路径, 尺寸, 像素比) 命中。
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..icon_utils import render_icon
from ..panels.style import panel_colors, rounded_path


@lru_cache(maxsize=64)
def _file_pixmap(path: str, size: int, dpr: float) -> QPixmap | None:
    """按设备像素比加载图片文件；缺失或解析失败返回 None（不缓存失败结果）。"""
    icon = QIcon(path)
    if icon.isNull():
        return None
    pixmap = icon.pixmap(QSize(size, size))
    if pixmap.isNull():
        return None
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def clear_icon_cache() -> None:
    """清空图片缓存（主题或资源根切换后调用）。"""
    _file_pixmap.cache_clear()


class CIconTile(QWidget):
    """图标方块：``icon`` 为内置图标名，``image`` 为插件自带的图片路径。"""

    def __init__(
        self,
        icon: str = "",
        size: int = 38,
        parent: QWidget | None = None,
        *,
        image: str = "",
    ):
        super().__init__(parent)
        self._icon = icon
        self._image = image
        self._size = max(24, int(size))
        self.setFixedSize(self._size, self._size)

    # ------------------------------------------------------------------
    def icon_name(self) -> str:
        return self._icon

    def image_path(self) -> str:
        return self._image

    def set_icon(self, icon: str = "", image: str = "") -> None:
        self._icon = icon
        self._image = image
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._size, self._size)

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        accent = QColor(colors["accent"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 12 if self._size >= 48 else 10)
        fill = QColor(accent)
        fill.setAlpha(30)
        painter.fillPath(path, fill)
        border = QColor(accent)
        border.setAlpha(85)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        inner = max(8, self._size - 16)
        dpr = max(1.0, float(self.devicePixelRatioF()))
        pixmap = _file_pixmap(self._image, round(inner * dpr), dpr) if self._image else None
        if pixmap is None:
            pixmap = render_icon(self._icon, QColor(colors["text"]), inner, dpr)
        if pixmap is not None and not pixmap.isNull():
            ratio = pixmap.devicePixelRatio() or 1.0
            width = pixmap.width() / ratio
            height = pixmap.height() / ratio
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()


__all__ = ["CIconTile", "clear_icon_cache"]
