"""把单色 SVG / QIcon 按当前文字色着色（供 Tag / Chip / Avatar 复用）。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPixmap

from ..icon_utils import render_icon


def tinted_pixmap(icon: str | QIcon | None, color, size: int, dpr: float = 1.0) -> QPixmap | None:
    """返回指定逻辑尺寸的单色图标（按 ``color`` 着色，结果缓存）。

    ``dpr`` 传控件的 ``devicePixelRatioF()``，高 DPI 下图标不再发虚。
    """
    if icon is None:
        return None
    return render_icon(icon, QColor(color), size, dpr)


__all__ = ["tinted_pixmap"]
