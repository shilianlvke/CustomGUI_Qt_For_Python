"""插件管理的工作区面板：列表面板、检查器面板与页内活动条。

列表与检查器都放在 ``CCard`` 上：卡片底色/描边由全局样式表维护，页面只
负责头部、空态与内容重排；这样主题切换不需要重建控件树，也不会在玻璃
背景上留下实色补丁。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import get_design_tokens
from sllkgui.guicore import CCard, CHDiv, CScrollArea, CText, single_shot

from .entries import StoreRow, label
from .theme import BUSY_OBJECT, text_role

_SPINNER_SIZE = 12
_SPINNER_INTERVAL = 16
_BODY_MAX_WIDTH = 760


class _Spinner(QWidget):
    """12px 旋转弧：只用令牌强调色，主题切换后下一次重绘即生效。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(_SPINNER_SIZE, _SPINNER_SIZE)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_SPINNER_INTERVAL)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(get_design_tokens().colors.accent), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawArc(rect, -self._angle * 16, 270 * 16)
        painter.end()


class BusyStrip(QWidget):
    """页内活动条：替代整页禁用，让用户仍能看见列表与当前选择。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName(BUSY_OBJECT)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(8)
        row.addWidget(_Spinner(self))
        self._text = CText("", pixel_size=10)
        text_role(self._text, "body")
        row.addWidget(self._text, 1)
        self.hide()

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def start(self, text: str) -> None:
        self._text.setText(text)
        self.show()

    def stop(self) -> None:
        self.hide()


class _Panel(CCard):
    """卡片 + 40px 头部 + 发丝线 + 内容区的通用面板。"""

    def __init__(self, parent=None) -> None:
        # CCard 的构造参数是 size 而不是 parent；加入页面布局时由 Qt 重新挂父级。
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._title = label("title", "", pixel_size=12, weight="semibold")
        self._meta = label("muted", "", pixel_size=10)
        head.addWidget(self._title)
        head.addWidget(self._meta)
        head.addStretch(1)
        outer.addLayout(head)
        outer.addWidget(CHDiv())
        self._outer = outer

    def set_titles(self, title: str, meta: str = "") -> None:
        if title != self._title.text():
            self._title.setText(title)
        if meta != self._meta.text():
            self._meta.setText(meta)


class ListPanel(_Panel):
    """列表面板：固定 400px，滚动区承载行；空态由页面构建后传入。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(400)
        self._rows: list[StoreRow] = []
        self._empty: QWidget | None = None

        self.scroll = CScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(2)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        self._outer.addWidget(self.scroll, 1)

    def rows(self) -> list[StoreRow]:
        return list(self._rows)

    def set_rows(self, rows: list[StoreRow]) -> None:
        self._clear()
        self._rows = list(rows)
        for row in self._rows:
            self.body_layout.insertWidget(self.body_layout.count() - 1, row)

    def sync_rows(self, rows: list[StoreRow]) -> None:
        """按给定顺序复用行：移除消失的行、插入新行，其余行保持原对象。

        只改变差集，滚动位置与未变化行都不会被重置。
        """
        if self._empty is not None:
            self._detach(self._empty)
            self._empty = None
        keep = {id(row) for row in rows}
        for row in list(self._rows):
            if id(row) not in keep:
                self._detach(row)
        self._rows = list(rows)
        for index, row in enumerate(self._rows):
            if self.body_layout.indexOf(row) != index:
                self.body_layout.insertWidget(index, row)
        self._ensure_trailing_stretch()

    def set_empty(self, widget: QWidget) -> None:
        self._clear()
        # 去掉 _clear 留下的尾部弹簧，让空态占满列表区域并垂直居中。
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            if item.widget() is None:
                continue
            item.widget().deleteLater()
        self._empty = widget
        self.body_layout.addWidget(widget, 1)

    def set_busy(self, busy: bool) -> None:
        for row in self._rows:
            row.set_busy(busy)

    def set_selected(self, record_id: str) -> None:
        for row in self._rows:
            row.set_selected(str(row.record.get("id") or "") == str(record_id or ""))

    def _ensure_trailing_stretch(self) -> None:
        layout = self.body_layout
        if layout.count() == 0 or layout.itemAt(layout.count() - 1).widget() is not None:
            layout.addStretch(1)

    def _detach(self, widget: QWidget) -> None:
        self.body_layout.removeWidget(widget)
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()

    def _clear(self) -> None:
        self._empty = None
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []
        self.body_layout.addStretch(1)


class InspectorPanel(_Panel):
    """检查器面板：内容最大 760px，避免宽屏下单列表单被拉得过散。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._content: QWidget | None = None
        self.scroll = CScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.body = QWidget()
        self.body.setMaximumWidth(_BODY_MAX_WIDTH)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(12)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        self._outer.addWidget(self.scroll, 1)

    def content(self) -> QWidget | None:
        return self._content

    def set_content(self, widget: QWidget) -> None:
        """替换详情内容：先挂新内容再移除旧内容，避免中间出现空白帧。

        替换期间关闭滚动区的刷新，并在同一轮内恢复滚动位置；未变化的
        内容（同一对象）直接跳过。
        """
        if widget is self._content:
            return
        bar = self.scroll.verticalScrollBar()
        previous = bar.value()
        old = self._content
        self.scroll.setUpdatesEnabled(False)
        try:
            self.body_layout.insertWidget(0, widget)
            self.body_layout.setStretch(0, 0)
            self.body_layout.setStretch(self.body_layout.count() - 1, 1)
            if old is not None:
                self.body_layout.removeWidget(old)
                old.hide()
                old.setParent(None)
                old.deleteLater()
            self._content = widget
            bar.setValue(min(previous, bar.maximum()))
        finally:
            self.scroll.setUpdatesEnabled(True)
        if previous > 0:
            single_shot(self, 0, lambda: bar.setValue(min(previous, bar.maximum())))


__all__ = ["BusyStrip", "InspectorPanel", "ListPanel"]
