"""树行绘制的几何与画笔工具。

两个委托（``CTree`` 与 ``CTreeTable``）共用同一套行内布局算法：箭头、复选框、
图标、文字依次向右排。抽到这里，两边的像素级外观才不会各写一遍后走样。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from sllkgui.appcore import AppSettings

from ...button.severity import contrast_text
from ...display.icon import tinted_pixmap
from ...display.palette import tokens
from ...paint_utils import draw_check
from ...panels.style import panel_colors, with_alpha
from .roles import NODE_ROLE

#: 每级缩进
INDENT = 18
#: 展开箭头占位
ARROW_SIZE = 16
#: 复选框尺寸
CHECKBOX_SIZE = 14
#: 节点图标尺寸
ICON_SIZE = 16
#: 行高
ROW_HEIGHT = 34


def _tree_config() -> tuple[int, int, int, int, int]:
    """(缩进, 箭头, 复选框, 图标, 行高)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.data
        return (
            int(cfg.tree_indent),
            int(cfg.tree_arrow_size),
            int(cfg.tree_checkbox_size),
            int(cfg.tree_icon_size),
            int(cfg.tree_row_height),
        )
    except Exception:
        return INDENT, ARROW_SIZE, CHECKBOX_SIZE, ICON_SIZE, ROW_HEIGHT


_ALIGN = {
    "left": Qt.AlignLeft | Qt.AlignVCenter,
    "center": Qt.AlignCenter,
    "right": Qt.AlignRight | Qt.AlignVCenter,
}


def _alignment(name: str) -> Qt.AlignmentFlag:
    return _ALIGN.get(name, _ALIGN["left"])


def _node_key(node: dict) -> Any:
    """节点选择键：优先 ``key``，其次 ``label``。"""
    if node.get("key") is not None:
        return node["key"]
    if node.get("label") is not None:
        return node["label"]
    return ""


def _node_label(node: dict) -> str:
    """节点展示文字：优先 ``label``，其次 ``key``。"""
    if node.get("label") is not None:
        return str(node["label"])
    if node.get("key") is not None:
        return str(node["key"])
    return ""


def _index_depth(index: QModelIndex) -> int:
    """索引在树中的层级（根为 0）。"""
    depth = 0
    parent = index.parent()
    while parent.isValid():
        depth += 1
        parent = parent.parent()
    return depth


def _row_metrics(
    rect: QRectF, index: QModelIndex, checkbox: bool
) -> tuple[QRectF | None, QRectF | None, float | None, float]:
    """计算一行中箭头、复选框、图标与文字的水平位置。"""
    indent, arrow_size, checkbox_size, icon_size, _ = _tree_config()
    x = rect.left() + 8 + _index_depth(index) * indent
    center_y = rect.center().y()

    arrow: QRectF | None = None
    model = index.model()
    if model is not None and model.rowCount(index) > 0:
        arrow = QRectF(x, center_y - arrow_size / 2, arrow_size, arrow_size)
        x += arrow_size + 2

    box: QRectF | None = None
    if checkbox:
        box = QRectF(x, center_y - checkbox_size / 2, checkbox_size, checkbox_size)
        x += checkbox_size + 6

    icon_x: float | None = None
    node = index.data(NODE_ROLE)
    if isinstance(node, dict) and node.get("icon") is not None:
        icon_x = x
        x += icon_size + 6

    return arrow, box, icon_x, x


def _paint_row_background(painter: QPainter, option: QStyleOptionViewItem) -> None:
    """按选中 / 悬停状态铺一层令牌色底。"""
    rect = QRectF(option.rect)
    if option.state & QStyle.StateFlag.State_Selected:
        # 与表格选中底色保持同一档（accent 18%），比原来的 14% 更容易识别
        painter.fillRect(rect, with_alpha(tokens()["accent"], 46))
    elif option.state & QStyle.StateFlag.State_MouseOver:
        painter.fillRect(rect, QColor(panel_colors()["hover"]))


def _paint_checkbox(painter: QPainter, box: QRectF, state: Qt.CheckState) -> None:
    colors = tokens()
    path = QPainterPath()
    path.addRoundedRect(box, 3, 3)
    if state == Qt.CheckState.Checked:
        painter.fillPath(path, QColor(colors["accent"]))
        draw_check(
            painter,
            box.adjusted(2, 2, -2, -2),
            contrast_text(QColor(colors["accent"])),
            1.8,
        )
        return
    if state == Qt.CheckState.PartiallyChecked:
        painter.fillPath(path, QColor(colors["accent"]))
        painter.setPen(QPen(contrast_text(QColor(colors["accent"])), 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            QPointF(box.left() + 3, box.center().y()),
            QPointF(box.right() - 3, box.center().y()),
        )
        return
    painter.fillPath(path, QColor(colors["surface"]))
    painter.setBrush(Qt.NoBrush)
    # 未勾选框的描边不能和填充同色（深色主题下两者都取 dark_four，
    # 框会直接“消失”在树底色里）；用正文色的低透明度描边保证可辨。
    painter.setPen(QPen(with_alpha(colors["text"], 110), 1))
    painter.drawPath(path)


def _paint_icon(
    painter: QPainter,
    index: QModelIndex,
    icon_x: float | None,
    center_y: float,
    color: QColor,
    dpr: float = 1.0,
) -> None:
    if icon_x is None:
        return
    node = index.data(NODE_ROLE)
    icon = node.get("icon") if isinstance(node, dict) else None
    if icon is None:
        return
    _, _, _, icon_size, _ = _tree_config()
    pixmap = tinted_pixmap(icon, color, icon_size, max(1.0, float(dpr)))
    if pixmap is not None:
        painter.drawPixmap(QPointF(icon_x, center_y - icon_size / 2), pixmap)


def _check_state(value: Any) -> Qt.CheckState:
    if value is None:
        return Qt.CheckState.Unchecked
    try:
        return Qt.CheckState(value)
    except (TypeError, ValueError):
        return Qt.CheckState.Unchecked
