"""插件管理单页工作台：已安装 / 发现 / 源。

设计目标：把原来三个 Surface 收进一个页面，用「模式导轨 + 工作区」组织：

- 左侧导轨：已安装 / 发现 / 源，带实时计数与状态指示；
- 已安装：自绘插件卡片 + 详情清单，悬停/选中都有明确反馈；
- 发现：``CPickList`` 把搜索结果挑选进安装队列，再批量安装；
- 源：``COrderList`` 管理优先级（顺序即解析顺序）与删除。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sllkgui.appcore import get_theme_manager
from sllkgui.guicore import CButton, CCard, CConfirmDialog, CInputText, COrderList, CPickList, CText
from sllkgui.guicore.custom_ui.panels.style import RADIUS, paint_surface, panel_colors, qss_color
from sllkgui.plugin import GalleryContext

_DANGER = "#e5534b"
_WARNING = "#d29922"


def _tint(color: str | QColor, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(alpha)
    return value


def _font(base: QFont, size: int, weight: QFont.Weight = QFont.Weight.Normal, *, mono: bool = False) -> QFont:
    font = QFont(base)
    font.setPixelSize(size)
    font.setWeight(weight)
    if mono:
        font.setFamilies(["Cascadia Mono", "Consolas", "Menlo", "monospace"])
    return font


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class _ModeCard(QFrame):
    """左侧模式导轨：自绘图标、标题、计数与选中强调条。"""

    clicked = Signal(str)

    def __init__(self, mode: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.title = title
        self._count = 0
        self._active = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_count(self, count: int) -> None:
        self._count = max(0, int(count))
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.mode)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = None
        border = None
        if self._active:
            background = _tint(colors["accent"], 34)
            border = _tint(colors["accent"], 96)
        elif self._hovered:
            background = colors["hover"]
        paint_surface(painter, rect, 10, background=background, border=border)

        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["accent"]))
            painter.drawRoundedRect(QRectF(rect.left() + 1, rect.top() + 13, 3, rect.height() - 26), 1.5, 1.5)

        glyph = QRectF(rect.left() + 14, rect.center().y() - 9, 18, 18)
        color = QColor(colors["accent"] if self._active else colors["muted"])
        self._draw_glyph(painter, glyph, color)

        text_color = QColor(colors["text"])
        painter.setPen(text_color)
        painter.setFont(_font(self.font(), 14, QFont.Weight.DemiBold if self._active else QFont.Weight.Medium))
        text_rect = QRectF(rect.left() + 42, rect.top(), rect.width() - 84, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        painter.setFont(_font(self.font(), 12))
        painter.setPen(QColor(colors["accent"] if self._active else colors["muted"]))
        count_rect = QRectF(rect.right() - 44, rect.top(), 32, rect.height())
        painter.drawText(count_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(self._count))
        painter.end()

    def _draw_glyph(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = rect.left()
        top = rect.top()
        width = rect.width()
        if self.mode == "installed":
            for index in range(3):
                painter.drawRoundedRect(QRectF(left, top + index * 6.4, width, 3.4), 1.7, 1.7)
            return
        if self.mode == "discover":
            painter.drawEllipse(QRectF(left + 1, top + 1, 11, 11))
            handle = QRectF(left + 10, top + 10, 6, 6)
            painter.drawLine(handle.topLeft(), handle.bottomRight())
            return
        for index in range(3):
            painter.drawEllipse(QRectF(left, top + index * 6.2, width, 4.2))


class _StatTile(QFrame):
    """顶部指标块：大数字 + 说明，自绘保证切主题即时生效。"""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.caption = caption
        self._value = "0"
        self.setFixedSize(108, 64)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_value(self, value: int | str) -> None:
        self._value = str(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_surface(painter, rect, RADIUS, background=colors["background"], border=colors["border"])
        painter.setPen(QColor(colors["accent"]))
        painter.setFont(_font(self.font(), 24, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(rect.left() + 12, rect.top() + 6, rect.width() - 24, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._value,
        )
        painter.setPen(QColor(colors["muted"]))
        painter.setFont(_font(self.font(), 11))
        painter.drawText(
            QRectF(rect.left() + 12, rect.bottom() - 26, rect.width() - 24, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.caption,
        )
        painter.end()


class _PluginCard(QFrame):
    """已安装插件卡片：名称、版本、状态与权限一屏读完。"""

    selected = Signal(str)

    def __init__(self, record: dict[str, Any], enabled_text: str, disabled_text: str, parent=None) -> None:
        super().__init__(parent)
        self.record = record
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self._selected = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def plugin_id(self) -> str:
        return str(self.record.get("id") or "")

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.selected.emit(self.plugin_id)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        background = colors["hover"] if self._hovered and not self._selected else colors["background"]
        border = QColor(colors["accent"]) if self._selected else QColor(colors["border"])
        paint_surface(painter, rect, RADIUS, background=background, border=border)
        if self._selected:
            painter.setPen(QPen(QColor(colors["accent"]), 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, RADIUS, RADIUS)

        name = str(self.record.get("name") or self.record.get("id") or "")
        version = f"v{self.record.get('version') or '?'}"
        enabled = bool(self.record.get("enabled"))
        painter.setFont(_font(self.font(), 14, QFont.Weight.DemiBold))
        painter.setPen(QColor(colors["text"]))
        metrics = QFontMetrics(painter.font())
        name_width = max(60, int(rect.width()) - 210)
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 10, name_width, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_width),
        )

        pill_font = _font(self.font(), 11, QFont.Weight.DemiBold)
        painter.setFont(pill_font)
        version_width = QFontMetrics(pill_font).horizontalAdvance(version) + 16
        pill = QRectF(rect.right() - version_width - 14, rect.top() + 10, version_width, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["accent"]))
        painter.drawRoundedRect(pill, 10, 10)
        painter.setPen(QColor(colors["on_accent"]))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, version)

        status_color = QColor(colors["accent"] if enabled else colors["muted"])
        painter.setBrush(status_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(pill.left() - 14, pill.center().y() - 3, 6, 6))
        painter.setFont(_font(self.font(), 11))
        painter.setPen(status_color)
        status_text = self._enabled_text if enabled else self._disabled_text
        painter.drawText(
            QRectF(pill.left() - 70, pill.top(), 52, pill.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            status_text,
        )

        painter.setFont(_font(self.font(), 11, mono=True))
        painter.setPen(QColor(colors["muted"]))
        sample = f"{self.record.get('id')} · {self.record.get('commit') or ''}"
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 34, rect.width() - 28, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(painter.font()).elidedText(sample, Qt.TextElideMode.ElideRight, int(rect.width()) - 28),
        )

        x = rect.left() + 14
        y = rect.top() + 60
        x += self._draw_pill(painter, x, y, str(self.record.get("source") or "-"), colors, accent=False)
        permissions = [str(item) for item in self.record.get("permissions") or []]
        for permission in permissions[:3]:
            x += self._draw_pill(painter, x, y, permission, colors, accent=False)
        if len(permissions) > 3:
            self._draw_pill(painter, x, y, f"+{len(permissions) - 3}", colors, accent=False)
        painter.end()

    @staticmethod
    def _draw_pill(painter: QPainter, x: float, y: float, text: str, colors: dict, *, accent: bool) -> float:
        font = _font(painter.font(), 11)
        painter.setFont(font)
        width = QFontMetrics(font).horizontalAdvance(text) + 16
        rect = QRectF(x, y, width, 20)
        painter.setBrush(_tint(colors["accent"], 30) if accent else Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QColor(colors["text"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        return width + 6


class _InstalledPanel(QWidget):
    """已安装：过滤、卡片、详情与操作。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._rows: list[dict[str, Any]] = []
        self._cards: list[_PluginCard] = []
        self._selected_id = ""
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = CInputText(placeholder=self.ctx.text("installed.filter", "过滤插件…"))
        self.filter.setFixedWidth(240)
        self.update_btn = CButton(self.ctx.text("installed.update", "更新"), size="sm")
        self.rollback_btn = CButton(
            self.ctx.text("installed.rollback", "回滚"), size="sm", severity="secondary", variant="outlined"
        )
        self.toggle_btn = CButton(
            self.ctx.text("installed.disable", "禁用"), size="sm", severity="warn", variant="outlined"
        )
        self.remove_btn = CButton(
            self.ctx.text("installed.remove", "卸载"), size="sm", severity="danger", variant="outlined"
        )
        toolbar.addWidget(self.filter)
        toolbar.addStretch(1)
        for button in (self.update_btn, self.rollback_btn, self.toggle_btn, self.remove_btn):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )
        self.cards_host = QWidget()
        self.cards_host.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 6, 0)
        self.cards_layout.setSpacing(8)
        self.scroll.setWidget(self.cards_host)
        body.addWidget(self.scroll, 1)
        body.addWidget(self._build_detail())
        layout.addLayout(body, 1)

        self.filter.textChanged.connect(self._rebuild_cards)
        self.update_btn.clicked.connect(lambda: self._run("update"))
        self.rollback_btn.clicked.connect(lambda: self._run("rollback"))
        self.toggle_btn.clicked.connect(self._toggle)
        self.remove_btn.clicked.connect(self._remove)
        self._update_actions()

    def _build_detail(self) -> QWidget:
        card = CCard()
        card.setFixedWidth(320)
        box = QVBoxLayout(card)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(8)
        box.addWidget(CText(self.ctx.text("installed.detail_title", "插件详情"), size="md", weight="semibold"))
        self.detail_hint = CText(self.ctx.text("installed.select_hint", "选择一个插件查看详情"), size="sm", wrap=True)
        box.addWidget(self.detail_hint)
        self.detail_grid = QGridLayout()
        self.detail_grid.setHorizontalSpacing(10)
        self.detail_grid.setVerticalSpacing(6)
        box.addLayout(self.detail_grid)
        self.detail_values: dict[str, CText] = {}
        for row, (key, caption) in enumerate(
            (
                ("version", self.ctx.text("installed.version", "版本")),
                ("source", self.ctx.text("installed.source", "来源")),
                ("commit", self.ctx.text("installed.commit", "提交")),
                ("path", self.ctx.text("installed.path", "目录")),
                ("permissions", self.ctx.text("installed.permissions", "权限")),
            )
        ):
            label = CText(caption, size="sm")
            value = CText("-", size="sm", wrap=True)
            self.detail_grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop)
            self.detail_grid.addWidget(value, row, 1)
            self.detail_values[key] = value
        box.addStretch(1)
        return card

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.page.runtime, "manager", None)

    def refresh(self) -> None:
        manager = self._manager()
        self._rows = list(manager.installed_rows()) if manager is not None else []
        if self._selected_id not in {row["id"] for row in self._rows}:
            self._selected_id = self._rows[0]["id"] if self._rows else ""
        self._rebuild_cards()
        self._show_detail()

    def _rebuild_cards(self) -> None:
        needle = self.filter.text().strip().lower() if hasattr(self, "filter") else ""
        _clear_layout(self.cards_layout)
        self._cards = []
        rows = [
            row
            for row in self._rows
            if not needle or needle in f"{row.get('id')} {row.get('source')}".lower()
        ]
        if not rows:
            empty = CText(self.ctx.text("installed.empty", "还没有安装插件"), size="md", wrap=True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(160)
            self.cards_layout.addWidget(empty)
        for row in rows:
            card = _PluginCard(
                row,
                self.ctx.text("installed.enabled", "已启用"),
                self.ctx.text("installed.disabled", "已禁用"),
            )
            card.set_selected(card.plugin_id == self._selected_id)
            card.selected.connect(self._select)
            self.cards_layout.addWidget(card)
            self._cards.append(card)
        self.cards_layout.addStretch(1)
        self._show_detail()

    def _select(self, plugin_id: str) -> None:
        self._selected_id = plugin_id
        for card in self._cards:
            card.set_selected(card.plugin_id == plugin_id)
        self._show_detail()
        self._update_actions()

    def _selected(self) -> dict[str, Any] | None:
        return next((row for row in self._rows if row.get("id") == self._selected_id), None)

    def _show_detail(self) -> None:
        row = self._selected()
        has_row = row is not None
        self.detail_hint.setVisible(not has_row)
        for value in self.detail_values.values():
            value.setVisible(has_row)
        if not row:
            return
        self.detail_values["version"].setText(str(row.get("version") or "-"))
        self.detail_values["source"].setText(str(row.get("source") or "-"))
        self.detail_values["commit"].setText(str(row.get("commit") or "-")[:12])
        self.detail_values["path"].setText(str(row.get("path") or "-"))
        self.detail_values["permissions"].setText(", ".join(row.get("permissions") or []) or "-")

    def _update_actions(self) -> None:
        row = self._selected()
        enabled = bool(row and row.get("enabled"))
        self.toggle_btn.setText(
            self.ctx.text("installed.disable", "禁用") if enabled else self.ctx.text("installed.enable", "启用")
        )
        for button in (self.update_btn, self.rollback_btn, self.toggle_btn, self.remove_btn):
            button.setEnabled(row is not None)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def _run(self, name: str) -> None:
        manager = self._manager()
        if manager is None or not self._selected_id:
            return
        plugin_id = self._selected_id
        try:
            with self.ctx.timing(f"core_store.{name}"):
                result = getattr(manager, name)(plugin_id)
            self.ctx.log(f"{name}: {result}")
            self.ctx.event(f"core_store.{name}", {"result": str(result)})
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"))
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self.ctx.report_error("CORE_STORE_ACTION_FAILED", f"{name} 失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self.refresh()
        self.page.refresh_stats()
        self.page.schedule_reload()

    def _toggle(self) -> None:
        row = self._selected()
        manager = self._manager()
        if row is None or manager is None:
            return
        manager.set_enabled(str(row["id"]), not bool(row.get("enabled")))
        self.refresh()
        self.page.refresh_stats()
        self.page.schedule_reload()

    def _remove(self) -> None:
        if not self._selected_id:
            return
        plugin_id = self._selected_id
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text("confirm.remove", "确定卸载该插件？数据目录默认保留。"),
            severity="danger",
        )
        if not ok:
            return
        manager = self._manager()
        if manager is None:
            return
        try:
            manager.remove(plugin_id)
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"))
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_REMOVE_FAILED", f"卸载失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self._selected_id = ""
        self.refresh()
        self.page.refresh_stats()
        self.page.schedule_reload()


class _DiscoverPanel(QWidget):
    """发现：搜索结果 → 安装队列。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._queue: list[dict[str, Any]] = []
        self._build()
        self.search()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.query = CInputText(placeholder=self.ctx.text("discover.placeholder", "搜索名称、ID 或简介…"))
        self.search_btn = CButton(self.ctx.text("discover.search", "搜索"), size="sm")
        self.refresh_btn = CButton(
            self.ctx.text("discover.refresh_sources", "刷新源"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        toolbar.addWidget(self.query, 1)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        hint = CText(self.ctx.text("discover.hint", "左侧挑选可安装插件，右侧是安装队列"), size="sm", wrap=True)
        layout.addWidget(hint)

        self.pick = CPickList()
        layout.addWidget(self.pick, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.queue_label = CText("", size="sm")
        self.clear_btn = CButton(self.ctx.text("discover.clear", "清空"), size="sm", severity="secondary", variant="text")
        self.install_btn = CButton(self.ctx.text("discover.install", "安装队列"), size="sm", severity="success")
        footer.addWidget(self.queue_label)
        footer.addStretch(1)
        footer.addWidget(self.clear_btn)
        footer.addWidget(self.install_btn)
        layout.addLayout(footer)

        self.search_btn.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.refresh_btn.clicked.connect(self._refresh_sources)
        self.clear_btn.clicked.connect(self._clear_queue)
        self.install_btn.clicked.connect(self._install)
        self.pick.changed.connect(self._on_changed)

    def _manager(self):
        return getattr(self.page.runtime, "manager", None)

    def _sources(self):
        return getattr(self.page.runtime, "sources", None)

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    def search(self) -> None:
        manager = self._manager()
        if manager is None:
            return
        installed = set(getattr(getattr(manager, "state", None), "plugins", {}) or {})
        queued = {str(item.get("id") or "") for item in self._queue}
        seen: set[str] = set()
        available: list[dict[str, Any]] = []
        for row in manager.search(self.query.text().strip()):
            plugin_id = str(row.get("id") or "")
            if not plugin_id or plugin_id in installed or plugin_id in queued or plugin_id in seen:
                continue
            seen.add(plugin_id)
            available.append(
                {
                    **row,
                    "label": f"{row.get('name') or plugin_id} · v{row.get('version') or '?'}",
                }
            )
        self.pick.set_values((available, list(self._queue)), emit=False)
        self._update_footer()
        self.ctx.log(f"search plugins: {len(available)}")
        self.ctx.event("core_store.search", {"count": len(available)})

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self.page.set_status(self.ctx.text("sources.refreshing", "正在刷新源…"))
        try:
            with self.ctx.timing("core_store.source_refresh"):
                sources.refresh_all()
            self.ctx.event("core_store.sources_refreshed")
            self.page.set_status(self.ctx.text("sources.refresh_done", "源刷新完成"))
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self.page.refresh_stats()
        self.search()

    # ------------------------------------------------------------------
    # 队列
    # ------------------------------------------------------------------
    def _on_changed(self, _source, target) -> None:
        self._queue = list(target)
        self._update_footer()

    def _update_footer(self) -> None:
        self.queue_label.setText(
            self.ctx.text("discover.queue_summary", "安装队列 · {count}").format(count=len(self._queue))
        )
        self.install_btn.setEnabled(bool(self._queue))
        self.clear_btn.setEnabled(bool(self._queue))

    def _clear_queue(self) -> None:
        self._queue = []
        self.search()

    def _install(self) -> None:
        if not self._queue:
            return
        manager = self._manager()
        if manager is None:
            return
        names = ", ".join(str(item.get("id")) for item in self._queue[:4])
        if len(self._queue) > 4:
            names += "…"
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("discover.install", "安装队列"),
            message=self.ctx.text("discover.confirm", "安装队列中的 {count} 个插件？\n{names}").format(
                count=len(self._queue), names=names
            ),
            severity="info",
        )
        if not ok:
            return
        installed = 0
        errors: list[str] = []
        for item in self._queue:
            plugin_id = str(item.get("id") or "")
            try:
                with self.ctx.timing("core_store.install"):
                    manager.install(plugin_id, source_id=str(item.get("source") or ""))
                installed += 1
                self.ctx.event("core_store.install", {"id": plugin_id, "version": item.get("version")})
            except Exception as exc:  # noqa: BLE001 - 单个失败不阻断队列
                errors.append(f"{plugin_id}: {exc}")
                self.ctx.report_error("CORE_STORE_INSTALL_FAILED", f"安装失败: {plugin_id}", str(exc))
        self._queue = []
        message = self.ctx.text("status.install_done", "已安装 {count} 个插件").format(count=installed)
        if errors:
            message += " · " + "; ".join(errors[:2])
        self.page.set_status(message, "error" if errors else "success")
        self.search()
        self.page.refresh_all()
        self.page.schedule_reload()


class _SourcesPanel(QWidget):
    """源：顺序即优先级，删除需确认。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._items: list[dict[str, Any]] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.url = CInputText(placeholder=self.ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_btn = CButton(self.ctx.text("sources.add", "添加"), size="sm")
        self.refresh_all_btn = CButton(
            self.ctx.text("sources.refresh_all", "全部刷新"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        add_row.addWidget(self.url, 1)
        add_row.addWidget(self.add_btn)
        add_row.addWidget(self.refresh_all_btn)
        layout.addLayout(add_row)

        self.order = COrderList()
        layout.addWidget(self.order, 1)

        hint = CText(self.ctx.text("sources.hint", "顺序即优先级，越靠前越先被采用"), size="sm", wrap=True)
        layout.addWidget(hint)

        self.add_btn.clicked.connect(self._add)
        self.url.returnPressed.connect(self._add)
        self.refresh_all_btn.clicked.connect(self._refresh_all)
        self.order.changed.connect(self._on_changed)

    def _sources(self):
        return getattr(self.page.runtime, "sources", None)

    def refresh(self) -> None:
        sources = self._sources()
        self._items = []
        if sources is not None:
            self._items = [
                {
                    "id": record.source_id,
                    "url": record.url,
                    "trust": record.trust,
                    "label": f"{record.source_id}  ·  {record.url}",
                }
                for record in sources.list()
            ]
        self.order.set_items(list(self._items), emit=False)

    def _on_changed(self, items) -> None:
        sources = self._sources()
        if sources is None:
            return
        new_ids = {str(item.get("id")) for item in items if item.get("id")}
        removed = [item for item in self._items if item["id"] not in new_ids]
        if removed:
            source_id = str(removed[0]["id"])
            ok = CConfirmDialog.ask(
                self,
                title=self.ctx.text("sources.remove", "移除源"),
                message=self.ctx.text("sources.confirm_remove", "移除源 {id}？已安装插件不受影响。").format(id=source_id),
                severity="warn",
            )
            if not ok:
                self.refresh()
                return
            for item in removed:
                try:
                    sources.remove(str(item["id"]))
                except Exception as exc:  # noqa: BLE001
                    self.ctx.report_error("CORE_STORE_SOURCE_REMOVE_FAILED", f"移除源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"))
            self.refresh()
            self.page.refresh_stats()
            return
        by_id = {record.source_id: record for record in sources.list()}
        ordered = [by_id[str(item["id"])] for item in items if item.get("id") in by_id]
        ordered += [record for record in sources.list() if record.source_id not in {item.source_id for item in ordered}]
        sources.state.sources = ordered
        sources.save()
        self._items = list(items)
        self.page.set_status(self.ctx.text("sources.order_saved", "已保存源优先级"))

    def _add(self) -> None:
        sources = self._sources()
        url = self.url.text().strip()
        if sources is None or not url:
            return
        try:
            record = sources.add(url, refresh=True)
            self.ctx.event("core_store.source_added", {"id": record.source_id})
            self.url.setText("")
            self.page.set_status(self.ctx.text("sources.added", "已添加源 {id}").format(id=record.source_id))
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_ADD_FAILED", f"添加源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self.refresh()
        self.page.refresh_stats()

    def _refresh_all(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self.page.set_status(self.ctx.text("sources.refreshing", "正在刷新源…"))
        try:
            with self.ctx.timing("core_store.source_refresh_all"):
                sources.refresh_all()
            self.ctx.event("core_store.sources_refreshed")
            self.page.set_status(self.ctx.text("sources.refresh_done", "源刷新完成"))
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self.refresh()


class StorePage(QWidget):
    """插件管理工作台。"""

    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        self._mode_cards: dict[str, _ModeCard] = {}
        self._build()
        self.switch_mode("installed")
        self.refresh_stats()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(12)

        hero = QHBoxLayout()
        hero.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = CText(self.ctx.text("store.title", "插件管理"), size="xl", weight="semibold")
        subtitle = CText(
            self.ctx.text("store.subtitle", "安装、更新与来源，在同一个工作台完成"),
            size="sm",
            wrap=True,
        )
        titles.addWidget(title)
        titles.addWidget(subtitle)
        hero.addLayout(titles, 1)

        self.stat_installed = _StatTile(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled = _StatTile(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources = _StatTile(self.ctx.text("stats.sources", "来源"))
        self.refresh_btn = CButton(self.ctx.text("store.refresh", "刷新"), size="sm", severity="secondary", variant="outlined")
        hero.addWidget(self.stat_installed)
        hero.addWidget(self.stat_enabled)
        hero.addWidget(self.stat_sources)
        hero.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(hero)

        body = QHBoxLayout()
        body.setSpacing(12)

        rail = QVBoxLayout()
        rail.setSpacing(6)
        for mode, key, caption in (
            ("installed", "modes.installed", "已安装"),
            ("discover", "modes.discover", "发现"),
            ("sources", "modes.sources", "源"),
        ):
            card = _ModeCard(mode, self.ctx.text(key, caption))
            card.clicked.connect(self.switch_mode)
            self._mode_cards[mode] = card
            rail.addWidget(card)
        rail.addStretch(1)
        rail_host = QWidget()
        rail_host.setLayout(rail)
        rail_host.setFixedWidth(228)
        body.addWidget(rail_host)

        self.stack = QStackedWidget()
        self.installed_panel = _InstalledPanel(self)
        self.discover_panel = _DiscoverPanel(self)
        self.sources_panel = _SourcesPanel(self)
        self.stack.addWidget(self.installed_panel)
        self.stack.addWidget(self.discover_panel)
        self.stack.addWidget(self.sources_panel)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.status = CText(self.ctx.text("status.ready", "就绪"), size="sm")
        root.addWidget(self.status)

        self.refresh_btn.clicked.connect(self.refresh_all)

    # ------------------------------------------------------------------
    # 模式
    # ------------------------------------------------------------------
    def switch_mode(self, mode: str) -> None:
        mapping = {
            "installed": self.installed_panel,
            "discover": self.discover_panel,
            "sources": self.sources_panel,
        }
        panel = mapping.get(mode)
        if panel is None:
            return
        self.stack.setCurrentWidget(panel)
        for key, card in self._mode_cards.items():
            card.set_active(key == mode)
        if mode == "installed":
            self.installed_panel.refresh()
        elif mode == "discover":
            self.discover_panel.search()
        else:
            self.sources_panel.refresh()

    # ------------------------------------------------------------------
    # 状态 / 刷新
    # ------------------------------------------------------------------
    def set_status(self, message: str, level: str = "info") -> None:
        colors = panel_colors()
        if level == "error":
            color = _DANGER
        elif level == "warning":
            color = _WARNING
        elif level == "success":
            color = qss_color(colors["accent"])
        else:
            color = qss_color(colors["muted"])
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(message)

    def refresh_stats(self) -> None:
        manager = getattr(self.runtime, "manager", None)
        rows = list(manager.installed_rows()) if manager is not None else []
        sources = getattr(self.runtime, "sources", None)
        source_count = len(sources.list()) if sources is not None else 0
        self.stat_installed.set_value(len(rows))
        self.stat_enabled.set_value(sum(1 for row in rows if row.get("enabled")))
        self.stat_sources.set_value(source_count)
        self._mode_cards["installed"].set_count(len(rows))
        self._mode_cards["sources"].set_count(source_count)

    def refresh_all(self) -> None:
        self.refresh_stats()
        self.installed_panel.refresh()
        self.discover_panel.search()
        self.sources_panel.refresh()
        self.set_status(self.ctx.text("status.ready", "就绪"))

    def schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            QTimer.singleShot(120, window.reload_plugins)

    def _theme_changed(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.update()


__all__ = ["StorePage"]
