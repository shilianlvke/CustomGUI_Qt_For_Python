"""背景层模糊：只对窗口背景 pixmap 做高斯模糊。

设计约束
--------
- **只作用于背景层**：模糊结果只是一个 ``QPixmap``，由 ``CWindow.paintEvent``
  画在背景位置；不挂 ``QGraphicsEffect`` 到窗口或任何子控件，宠物、文字与
  前景图层的栅格化过程完全不受影响。
- **边缘不透明**：模糊会把源图的透明边缘向内扩散，直接裁回窗口会形成一圈
  半透明黑边。这里先把四周的 1px 边缘拉伸成同等宽度的补边，再模糊并裁回
  窗口尺寸，窗口四角仍然是连续的背景色。
- **零值 / 空图快速返回**：调用方在无背景图或强度为 0 时不会进入渲染，
  这里再做一次防御，保证纯色 / 透明背景不报错。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene

#: 补边至少 6px：半径很小时也要给模糊核留出过渡空间。
_MIN_PADDING = 6


def _expanded_with_edge_bleed(surface: QPixmap, padding: int) -> QPixmap:
    """把窗口背景放进带补边的画布，并用边缘拉伸填满四周。

    只从源图取 1px 的边缘条拉伸，不改变窗口内实际背景的缩放结果；
    模糊后这些补边会被裁掉，只留下自然的边缘过渡。
    """
    width, height = surface.width(), surface.height()
    canvas = QPixmap(width + padding * 2, height + padding * 2)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(padding, padding, surface)
    full_w = width + padding * 2
    full_h = height + padding * 2
    # 上下边缘条铺满整宽，左右边缘条再覆盖四角，形成闭合的补边框。
    painter.drawPixmap(QRectF(0, 0, full_w, padding), surface, QRectF(0, 0, width, 1))
    painter.drawPixmap(QRectF(0, padding + height, full_w, padding), surface, QRectF(0, height - 1, width, 1))
    painter.drawPixmap(QRectF(0, 0, padding, full_h), surface, QRectF(0, 0, 1, height))
    painter.drawPixmap(QRectF(width + padding, 0, padding, full_h), surface, QRectF(width - 1, 0, 1, height))
    painter.end()
    return canvas


def blur_background(surface: QPixmap, radius: int) -> QPixmap:
    """返回窗口尺寸的模糊背景；``radius <= 0`` 或空图时原样返回。

    ``radius`` 为逻辑像素，与设置项 ``background_blur`` 的单位一致。
    """
    if surface.isNull() or radius <= 0 or surface.width() <= 0 or surface.height() <= 0:
        return surface

    padding = max(_MIN_PADDING, int(radius) * 3)
    canvas = _expanded_with_edge_bleed(surface, padding)

    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, canvas.width(), canvas.height())
    item = QGraphicsPixmapItem(canvas)
    # 画布已包含补边：item 必须贴在场景原点，窗口内背景位于 (padding, padding)，
    # 这样模糊核的衰减只发生在补边区，裁回后窗口四角仍是实色。
    item.setPos(0, 0)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(float(radius))
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    rendered = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
    rendered.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rendered)
    scene.render(painter, QRectF(rendered.rect()), QRectF(0, 0, canvas.width(), canvas.height()))
    painter.end()
    scene.removeItem(item)

    cropped = rendered.copy(padding, padding, surface.width(), surface.height())
    return QPixmap.fromImage(cropped)


__all__ = ["blur_background"]
