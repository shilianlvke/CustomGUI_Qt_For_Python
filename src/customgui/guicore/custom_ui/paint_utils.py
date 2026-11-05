"""自绘组件共用的图形小工具（勾、叉、箭头、日历、星形）。"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF


def _pen(color, width: float) -> QPen:
    return QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def draw_check(painter: QPainter, rect: QRectF, color, width: float = 1.8) -> None:
    """在矩形内画一个对勾。"""
    path = QPainterPath()
    path.moveTo(rect.left() + rect.width() * 0.16, rect.top() + rect.height() * 0.52)
    path.lineTo(rect.left() + rect.width() * 0.40, rect.top() + rect.height() * 0.76)
    path.lineTo(rect.left() + rect.width() * 0.84, rect.top() + rect.height() * 0.26)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(_pen(color, width))
    painter.drawPath(path)


def draw_cross(painter: QPainter, rect: QRectF, color, width: float = 1.5) -> None:
    """在矩形内画一个 ×。"""
    painter.setBrush(Qt.NoBrush)
    painter.setPen(_pen(color, width))
    inset = rect.width() * 0.24
    painter.drawLine(
        QPointF(rect.left() + inset, rect.top() + inset),
        QPointF(rect.right() - inset, rect.bottom() - inset),
    )
    painter.drawLine(
        QPointF(rect.right() - inset, rect.top() + inset),
        QPointF(rect.left() + inset, rect.bottom() - inset),
    )


def draw_chevron(
    painter: QPainter, center: QPointF, color, size: float = 7.0, direction: str = "down", width: float = 1.6
) -> None:
    """在中心点画一个箭头（down / up / left / right）。"""
    half = size / 2
    path = QPainterPath()
    if direction == "down":
        path.moveTo(center.x() - half, center.y() - half * 0.45)
        path.lineTo(center.x(), center.y() + half * 0.45)
        path.lineTo(center.x() + half, center.y() - half * 0.45)
    elif direction == "up":
        path.moveTo(center.x() - half, center.y() + half * 0.45)
        path.lineTo(center.x(), center.y() - half * 0.45)
        path.lineTo(center.x() + half, center.y() + half * 0.45)
    elif direction == "left":
        path.moveTo(center.x() + half * 0.45, center.y() - half)
        path.lineTo(center.x() - half * 0.45, center.y())
        path.lineTo(center.x() + half * 0.45, center.y() + half)
    else:
        path.moveTo(center.x() - half * 0.45, center.y() - half)
        path.lineTo(center.x() + half * 0.45, center.y())
        path.lineTo(center.x() - half * 0.45, center.y() + half)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(_pen(color, width))
    painter.drawPath(path)


def draw_calendar(painter: QPainter, rect: QRectF, color, width: float = 1.4) -> None:
    """在矩形内画一个日历图标。"""
    painter.setBrush(Qt.NoBrush)
    painter.setPen(_pen(color, width))
    body = QRectF(rect.left(), rect.top() + rect.height() * 0.12, rect.width(), rect.height() * 0.82)
    painter.drawRoundedRect(body, 2.5, 2.5)
    painter.drawLine(
        QPointF(rect.left(), rect.top() + rect.height() * 0.38),
        QPointF(rect.right(), rect.top() + rect.height() * 0.38),
    )
    for ratio in (0.3, 0.7):
        x = rect.left() + rect.width() * ratio
        painter.drawLine(
            QPointF(x, rect.top() + rect.height() * 0.02),
            QPointF(x, rect.top() + rect.height() * 0.22),
        )


def star_path(center: QPointF, outer: float, inner: float | None = None) -> QPainterPath:
    """以中心点生成五角星路径。"""
    inner = inner if inner is not None else outer * 0.44
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(-90 + index * 36)
        points.append(QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle)))
    polygon = QPolygonF(points)
    path = QPainterPath()
    path.addPolygon(polygon)
    path.closeSubpath()
    return path


#: 阴影溢出控件盒子的量（左, 上, 右, 下）：控件要留出这块透明边距，本体画在缩小后的矩形里
SHADOW_MARGINS = (3, 1, 3, 4)

#: Fluent 高度阴影：短距离、低不透明度，拆成 (下移, 外扩, 透明度) 三层
FLUENT_SHADOW_LAYERS = (
    (2, -1, 30),
    (1, 0, 20),
    (1, 2, 12),
)

#: 兼容旧名（0.x 内测期保留）；新代码请使用 :data:`FLUENT_SHADOW_LAYERS`
AURA_SHADOW_LAYERS = FLUENT_SHADOW_LAYERS


def shadow_layers(
    body_path: QPainterPath,
    body_rect: QRectF,
    radius: float,
    layers: tuple[tuple[int, int, int], ...] = FLUENT_SHADOW_LAYERS,
) -> list[tuple[QPainterPath, QColor]]:
    """生成「只落在按钮本体之外」的阴影层，供调用方自行缓存。

    Qt 的绘制被裁剪在控件矩形内，因此使用前必须给控件留出 :data:`SHADOW_MARGINS`
    的透明边距，本体画在缩小后的矩形里，阴影才有地方落。
    """
    result: list[tuple[QPainterPath, QColor]] = []
    for offset_y, spread, alpha in layers:
        rect = body_rect.adjusted(-spread, -spread + offset_y, spread, spread + offset_y)
        layer = QPainterPath()
        layer.addRoundedRect(rect, radius + max(0, spread), radius + max(0, spread))
        result.append((layer.subtracted(body_path), QColor(0, 0, 0, alpha)))
    return result


def draw_shadow(painter: QPainter, body_path: QPainterPath, body_rect: QRectF, radius: float) -> None:
    """直接画阴影（不做缓存；低频重绘的浮层用，高频重绘请自建缓存）。"""
    for layer, color in shadow_layers(body_path, body_rect, radius):
        painter.fillPath(layer, color)


__all__ = [
    "AURA_SHADOW_LAYERS",
    "FLUENT_SHADOW_LAYERS",
    "draw_calendar",
    "draw_check",
    "draw_chevron",
    "draw_cross",
    "draw_shadow",
    "shadow_layers",
    "star_path",
]
