"""把单色 SVG / QIcon 按当前文字色着色（供 Tag / Chip / Avatar 复用）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from AppCore import PathFactory

_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def tinted_pixmap(icon: str | QIcon | None, color, size: int) -> QPixmap | None:
    """返回指定尺寸的单色图标（按 ``color`` 着色，结果缓存）。"""
    if icon is None:
        return None
    if isinstance(icon, QIcon):
        pixmap = icon.pixmap(size, size)
        if pixmap.isNull():
            return None
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return pixmap

    path = PathFactory.set_svg_icon(icon)
    key = (path, QColor(color).name(), size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    source = QPixmap(path)
    if source.isNull():
        return None
    pixmap = source.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    _CACHE[key] = pixmap
    return pixmap


__all__ = ["tinted_pixmap"]
