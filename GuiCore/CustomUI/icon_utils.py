"""图标加载与着色（按设备像素比栅格化，供自绘组件共用）。

之前 ``CButton`` 里按 1x 栅格化再绘制，4K 屏 / 125% 缩放下图标会发虚。
这里统一按 ``devicePixelRatioF()`` 生成位图并 ``setDevicePixelRatio``，
绘制时仍使用逻辑像素，物理像素自动翻倍。
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from AppCore import PathFactory


def icon_path(source: str) -> str:
    """图标名（``icon_users``）或绝对路径 → 绝对路径。"""
    if os.path.isabs(source):
        return source
    return PathFactory.set_svg_icon(source)


#: 字符串图标的栅格化缓存（键：路径、颜色、逻辑尺寸、像素比）
_CACHE: dict[tuple[str, str, int, float], QPixmap] = {}


def render_icon(
    source: str | QIcon | None,
    color: QColor,
    size: int,
    dpr: float = 1.0,
) -> QPixmap | None:
    """把图标渲染成 ``color`` 单色位图（逻辑尺寸 ``size``）。

    ``dpr`` 传控件的 ``devicePixelRatioF()``；返回的 pixmap 已带同样的
    devicePixelRatio，调用方直接按逻辑坐标绘制即可。字符串图标按
    (路径, 颜色, 尺寸, dpr) 缓存，切主题换色时颜色参与键值自动区分。
    """
    if source is None:
        return None

    ratio = max(1.0, float(dpr))
    if isinstance(source, str):
        key = (icon_path(source), QColor(color).name(), max(1, round(size)), round(ratio, 2))
        cached = _CACHE.get(key)
        if cached is not None:
            return cached

    target = max(1, round(size * ratio))

    if isinstance(source, QIcon):
        pixmap = source.pixmap(QSize(target, target))
    else:
        pixmap = QPixmap(icon_path(source))
        if pixmap.isNull():
            return None
        pixmap = pixmap.scaled(target, target, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    if pixmap.isNull():
        return None

    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()
    tinted.setDevicePixelRatio(ratio)

    if isinstance(source, str):
        _CACHE[key] = tinted
    return tinted


__all__ = ["icon_path", "render_icon"]
