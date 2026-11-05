"""时间线（Windows Fluent Design Timeline）。

- 事件数据为 ``list[dict]``，字段 ``date/title/description/icon/severity``；
- 轴线与圆点自绘，事件卡片由 ``QLabel`` 组成，便于换行与主题跟随；
- 支持 ``align="left"/"right"/"alternate"`` 与
  ``layout="vertical"/"horizontal"``；
- 颜色实时读取 :func:`~..display.palette.tokens` 与
  :func:`~..panels.style.panel_colors`，主题切换后调用 ``update()`` 即可重绘。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings

from ...acrylic import glass_surface
from ..button.severity import contrast_text, normalize_severity, severity_color
from ..display.icon import tinted_pixmap
from ..display.palette import tokens
from ..panels.style import panel_colors, panel_font, with_alpha

#: 圆点半径
DOT_RADIUS = 6
#: 圆点光晕半径
HALO_RADIUS = 10
#: 轴线距控件边缘的距离
AXIS_MARGIN = 24
#: 轴线与卡片的间距
CARD_GAP = 22
#: 控件内边距
EDGE = 12
#: 事件之间的间距
SPACING = 14
#: 横向布局时卡片的理想宽度
HORIZONTAL_CARD_WIDTH = 200
#: 横向布局时轴线距顶部的最小距离
AXIS_TOP = 16
#: 圆点与卡片内容的垂直偏移
DOT_OFFSET = 18
#: 横向布局时轴线与卡片的间距
DOT_GAP = 18


def _timeline_config() -> tuple[int, int, int, int, int, int, int, int, int, int]:
    """(点半径, 光晕半径, 轴线边距, 卡片间距, 内边距, 事件间距,
    横向卡片宽度, 轴顶距, 点偏移, 横向点间距)。"""
    try:
        cfg = AppSettings.data
        return (
            int(cfg.timeline_dot_radius),
            int(cfg.timeline_halo_radius),
            int(cfg.timeline_axis_margin),
            int(cfg.timeline_card_gap),
            int(cfg.timeline_edge),
            int(cfg.timeline_spacing),
            int(cfg.timeline_horizontal_card_width),
            int(cfg.timeline_axis_top),
            int(cfg.timeline_dot_offset),
            int(cfg.timeline_dot_gap),
        )
    except Exception:  # 配置上下文未就绪时用兜底值
        return (
            DOT_RADIUS,
            HALO_RADIUS,
            AXIS_MARGIN,
            CARD_GAP,
            EDGE,
            SPACING,
            HORIZONTAL_CARD_WIDTH,
            AXIS_TOP,
            DOT_OFFSET,
            DOT_GAP,
        )


class _TimelineCard(QFrame):
    """单个时间线事件卡片：日期、标题、描述。"""

    def __init__(self, index: int, event: dict, parent=None):
        super().__init__(parent)
        self._index = index
        self.setObjectName("CTimeline_Card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        self._date = QLabel(str(event.get("date") or ""), self)
        self._date.setFont(panel_font(11, QFont.Weight.Normal))
        self._date.setWordWrap(True)
        if not event.get("date"):
            self._date.setVisible(False)

        self._title = QLabel(str(event.get("title") or ""), self)
        self._title.setFont(panel_font(13, QFont.Weight.DemiBold))
        self._title.setWordWrap(True)

        self._description = QLabel(str(event.get("description") or ""), self)
        self._description.setFont(panel_font(12, QFont.Weight.Normal))
        self._description.setWordWrap(True)
        if not event.get("description"):
            self._description.setVisible(False)

        layout.addWidget(self._date)
        layout.addWidget(self._title)
        layout.addWidget(self._description)

    def preferred_height(self, width: int) -> int:
        """在给定宽度下计算卡片高度（供手动几何排版使用）。"""
        width = max(100, int(width))
        self.setFixedWidth(width)
        layout = self.layout()
        height = -1
        if layout is not None:
            layout.activate()
            if layout.hasHeightForWidth():
                height = layout.heightForWidth(width)
        if height <= 0:
            height = self.sizeHint().height()
        return max(48, int(height))

    def refresh_theme(self) -> None:
        """按当前主题刷新子标签文字色。"""
        colors = tokens()
        self._date.setStyleSheet(f"color: {colors['muted']}; background: transparent;")
        self._title.setStyleSheet(f"color: {colors['text']}; background: transparent;")
        self._description.setStyleSheet(f"color: {colors['muted']}; background: transparent;")
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        colors = tokens()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        # 事件卡片跟随亚克力强度，避免在玻璃页面上形成不透明色块
        painter.fillPath(path, glass_surface(colors["surface"], AppSettings.glass.card, minimum=0.10))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawPath(path)
        painter.end()


class CTimeline(QWidget):
    """时间线组件。

    Args:
        events: ``list[dict]``，字段 ``date/title/description/icon/severity``。
        align: ``"left"`` / ``"right"`` / ``"alternate"``。
        layout: ``"vertical"`` / ``"horizontal"``。

    Signals:
        itemClicked(int): 点击事件卡片时发出事件下标。
    """

    itemClicked = Signal(int)

    def __init__(
        self,
        events: list[dict] | None = None,
        align: str = "left",
        layout: str = "vertical",
        parent=None,
    ):
        super().__init__(parent)
        (
            self._dot_radius,
            self._halo_radius,
            self._axis_margin,
            self._card_gap,
            self._edge,
            self._spacing,
            self._horizontal_card_width,
            self._axis_top,
            self._dot_offset,
            self._dot_gap,
        ) = _timeline_config()
        self.setObjectName("CTimeline_Widget")
        self._events: list[dict] = []
        self._cards: list[_TimelineCard] = []
        self._align = "left"
        self._layout_mode = "vertical"
        self._dots: list[QPointF] = []
        self._line_start = QPointF()
        self._line_end = QPointF()
        self._axis_vertical = True
        self._theme_signature: tuple | None = None

        self.set_align(align)
        self.set_layout(layout)
        self.set_events(events or [])

    # ------------------------------------------------------------------
    # 数据与配置
    # ------------------------------------------------------------------
    def events(self) -> list[dict]:
        return list(self._events)

    def set_events(self, events: list[dict]) -> None:
        """整体替换事件列表并重建卡片。"""
        self._events = [dict(event) for event in events if isinstance(event, dict)]
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        for index, event in enumerate(self._events):
            card = _TimelineCard(index, event, self)
            card.installEventFilter(self)
            card.show()
            self._cards.append(card)

        # 新卡片需要重新套用当前主题色
        self._theme_signature = None
        self._relayout()
        self.updateGeometry()
        self.update()

    def align(self) -> str:
        return self._align

    def set_align(self, align: str) -> None:
        """设置卡片相对轴线的位置：left / right / alternate。"""
        self._align = align if align in ("left", "right", "alternate") else "left"
        self._relayout()
        self.update()

    def layout_mode(self) -> str:
        return self._layout_mode

    def set_layout(self, layout: str) -> None:
        """设置轴线方向：vertical / horizontal。"""
        self._layout_mode = "horizontal" if layout == "horizontal" else "vertical"
        self._relayout()
        self.updateGeometry()
        self.update()

    def cards(self) -> list[QWidget]:
        """返回事件卡片控件（按事件顺序）。"""
        return list(self._cards)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802
        if not self._dots:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        colors = tokens()
        painter.setPen(QPen(QColor(colors["surface_strong"]), 2))
        painter.drawLine(self._line_start, self._line_end)

        for event, dot in zip(self._events, self._dots, strict=False):
            base = _severity_color(event.get("severity"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(base, 40))
            painter.drawEllipse(dot, self._halo_radius, self._halo_radius)
            painter.setBrush(base)
            painter.drawEllipse(dot, self._dot_radius, self._dot_radius)
            icon = event.get("icon")
            if icon is not None:
                pixmap = tinted_pixmap(icon, contrast_text(base), 12, self.devicePixelRatioF())
                if pixmap is not None:
                    painter.drawPixmap(
                        QPointF(dot.x() - 6, dot.y() - 6),
                        pixmap,
                    )
        painter.end()

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def update(self, *args):  # noqa: N802
        self._apply_theme()
        super().update()

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._theme_signature = None
            self._apply_theme()

    def _apply_theme(self) -> None:
        signature = (tuple(sorted(tokens().items())), tuple(sorted(panel_colors().items())))
        if signature == self._theme_signature:
            return
        self._theme_signature = signature
        for card in self._cards:
            card.refresh_theme()

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def sizeHint(self) -> QSize:  # noqa: N802
        count = len(self._events)
        if self._layout_mode == "vertical":
            return QSize(420, max(160, count * 92 + self._edge * 2))
        return QSize(max(360, count * (self._horizontal_card_width + self._spacing) + self._edge * 2), 280)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, 120)

    def _relayout(self) -> None:
        if not self._cards:
            self._dots = []
            return
        width = max(200, self.width())
        if self._layout_mode == "vertical":
            self._layout_vertical(width)
        else:
            self._layout_horizontal(width)
        self.update()

    def _layout_vertical(self, width: int) -> None:
        edge = self._edge
        gap = self._card_gap
        if self._align == "alternate":
            axis = width / 2
        elif self._align == "right":
            axis = width - self._axis_margin
        else:
            axis = self._axis_margin

        y = edge
        dots: list[QPointF] = []
        for index, card in enumerate(self._cards):
            if self._align == "left":
                x = axis + gap
                card_width = width - axis - gap - edge
            elif self._align == "right":
                x = edge
                card_width = axis - gap - edge
            elif index % 2 == 0:
                x = axis + gap
                card_width = width - axis - gap - edge
            else:
                x = edge
                card_width = axis - gap - edge

            card_width = max(120, int(card_width))
            height = card.preferred_height(card_width)
            card.setGeometry(int(x), int(y), card_width, height)
            dots.append(QPointF(axis, y + self._dot_offset))
            y += height + self._spacing

        self._dots = dots
        self._axis_vertical = True
        self._line_start = QPointF(axis, dots[0].y())
        self._line_end = QPointF(axis, dots[-1].y())

    def _layout_horizontal(self, width: int) -> None:
        edge = self._edge
        count = len(self._cards)
        available = width - edge * 2 - self._spacing * (count - 1)
        card_width = max(120, min(self._horizontal_card_width, int(available / count)))
        content_width = card_width * count + self._spacing * (count - 1)
        start = max(edge, (width - content_width) / 2)

        heights = [card.preferred_height(card_width) for card in self._cards]
        max_height = max(heights)

        if self._align == "right":
            axis_y = edge + max_height + self._dot_gap
        elif self._align == "alternate":
            above = [height for index, height in enumerate(heights) if index % 2 == 1]
            axis_y = edge + (max(above) if above else 0) + self._dot_gap
        else:
            axis_y = self._axis_top

        dots: list[QPointF] = []
        for index, card in enumerate(self._cards):
            x = int(start + index * (card_width + self._spacing))
            if self._align == "left":
                y = axis_y + self._dot_gap
            elif self._align == "right":
                y = axis_y - self._dot_gap - heights[index]
            elif index % 2 == 0:
                y = axis_y + self._dot_gap
            else:
                y = axis_y - self._dot_gap - heights[index]
            card.setGeometry(x, int(y), card_width, heights[index])
            dots.append(QPointF(x + card_width / 2, axis_y))

        self._dots = dots
        self._axis_vertical = False
        self._line_start = QPointF(dots[0].x(), axis_y)
        self._line_end = QPointF(dots[-1].x(), axis_y)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress:
            for index, card in enumerate(self._cards):
                if watched is card:
                    self.itemClicked.emit(index)
                    break
        return super().eventFilter(watched, event)


def _severity_color(value) -> QColor:
    """事件严重度对应的圆点颜色（未知值回落到 primary）。"""
    try:
        severity = normalize_severity(value if value is not None else "primary")
    except ValueError:
        severity = normalize_severity("primary")
    return severity_color(severity)


__all__ = ["CTimeline"]
