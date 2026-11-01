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


__all__ = ["draw_calendar", "draw_check", "draw_chevron", "draw_cross", "star_path"]
