"""插件管理单页：编辑式控制台。

一页三段，按「已安装 → 发现 → 来源」自上而下阅读：

- 顶部是标题与三个指标（已安装 / 启用 / 来源），只做概览，不抢焦点；
- 已安装：整行卡片，名称、版本、状态、来源、权限与操作同屏，不需要选中再看；
- 发现：搜索框 + 两列结果卡片，每张卡片直接「安装」；
- 来源：紧凑行 + 添加输入，官方/用户信任用标签区分。

设计约束：不使用 CPickList / COrderList；列表与卡片均为自绘表面，颜色实时
取自 ``panel_colors()``，切主题无需重建。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sllkgui.appcore import get_theme_manager
from sllkgui.guicore import CButton, CConfirmDialog, CInputText, CText
from sllkgui.guicore.custom_ui.panels.style import RADIUS, paint_surface, panel_colors, qss_color
from sllkgui.plugin import GalleryContext

_DANGER = "#e5534b"
_WARNING = "#d29922"
_MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "monospace"]


# ----------------------------------------------------------------------
# 绘制工具
# ----------------------------------------------------------------------
def _tint(color: str | QColor, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(alpha)
    return value


def _font(base: QFont, size: int, weight: QFont.Weight = QFont.Weight.Normal, *, mono: bool = False) -> QFont:
    font = QFont(base)
    font.setPixelSize(size)
    font.setWeight(weight)
    if mono:
        font.setFamilies(_MONO_FAMILIES)
    return font


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _card_rect(widget: QWidget) -> QRectF:
    return QRectF(widget.rect()).adjusted(0.75, 0.75, -0.75, -0.75)


class _Chip(QWidget):
    """胶囊标签：版本、状态、来源、权限共用。"""

    def __init__(self, text: str, *, accent: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._accent = accent
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._resize_to_text()

    def _font(self) -> QFont:
        return _font(self.font(), 11, QFont.Weight.Medium)

    def _resize_to_text(self) -> None:
        width = QFontMetrics(self._font()).horizontalAdvance(self._text) + 16
        self.setFixedWidth(max(28, width))

    def set_text(self, text: str, *, accent: bool | None = None) -> None:
        self._text = text
        if accent is not None:
            self._accent = accent
        self._resize_to_text()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = _tint(colors["accent"], 38) if self._accent else None
        border = _tint(colors["accent"], 110) if self._accent else QColor(colors["border"])
        paint_surface(painter, rect, 10, background=background, border=border)
        painter.setFont(self._font())
        painter.setPen(QColor(colors["accent"] if self._accent else colors["muted"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class _ElidedLabel(QWidget):
    """单行省略文本：用于 ID、commit、URL 等不应换行的内容。"""

    def __init__(self, text: str = "", *, mono: bool = False, size: int = 11, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._mono = mono
        self._size = size
        self.setFixedHeight(size + 5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setFont(_font(self.font(), self._size, mono=self._mono))
        painter.setPen(QColor(colors["muted"]))
        metrics = QFontMetrics(painter.font())
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(self._text, Qt.TextElideMode.ElideRight, max(0, self.width())),
        )
        painter.end()


class _Rule(QWidget):
    """一条会随主题变色的细线。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setPen(QPen(QColor(panel_colors()["divider"]), 1))
        y = self.height() / 2
        painter.drawLine(0, int(y), self.width(), int(y))
        painter.end()


class _IndexTitle(QWidget):
    """章节标题：「01」用强调色，标题用正文色。"""

    def __init__(self, index: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self._title = title
        self.setFixedHeight(28)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(_font(self.font(), 16, QFont.Weight.DemiBold))
        return QSize(metrics.horizontalAdvance(self._title) + 44, 28)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        index_font = _font(self.font(), 11, QFont.Weight.DemiBold, mono=True)
        painter.setFont(index_font)
        painter.setPen(QColor(colors["accent"]))
        painter.drawText(
            QRectF(0, 0, 28, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._index,
        )
        painter.setFont(_font(self.font(), 16, QFont.Weight.DemiBold))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(30, 0, self.width() - 30, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._title,
        )
        painter.end()


class _SectionHeader(QWidget):
    """章节头：序号 + 标题 + 分隔线 + 右侧动作。"""

    def __init__(self, index: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title_widget = _IndexTitle(index, title, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)
        layout.addWidget(self.title_widget)
        layout.addWidget(_Rule(self), 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        layout.addLayout(self.actions)
        self.setFixedHeight(34)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)


class _StatChip(QWidget):
    """指标：强调色圆点 + 数字 + 说明，无外框，保持版面轻盈。"""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.caption = caption
        self._value = 0
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_value(self, value: int) -> None:
        self._value = int(value)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(_font(self.font(), 11))
        return QSize(metrics.horizontalAdvance(self.caption) + 58, 34)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["accent"]))
        painter.drawEllipse(QRectF(2, self.height() / 2 - 3, 6, 6))
        painter.setFont(_font(self.font(), 17, QFont.Weight.DemiBold))
        painter.setPen(QColor(colors["text"]))
        value_text = str(self._value)
        metrics = QFontMetrics(painter.font())
        painter.drawText(
            QRectF(16, 0, metrics.horizontalAdvance(value_text) + 4, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            value_text,
        )
        painter.setFont(_font(self.font(), 11))
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(
            QRectF(16 + metrics.horizontalAdvance(value_text) + 8, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.caption,
        )
        painter.end()


class _EmptyCard(QFrame):
    """空态：虚线感圆角卡片 + 居中提示。"""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self.setMinimumHeight(84)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = _card_rect(self)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(colors["border"]), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        painter.setFont(_font(self.font(), 12))
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class _PluginRow(QFrame):
    """已安装插件：整行卡片，信息与操作同屏。"""

    def __init__(
        self,
        record: dict[str, Any],
        texts: dict[str, str],
        on_update: Callable[[str], None],
        on_rollback: Callable[[str], None],
        on_toggle: Callable[[str], None],
        on_remove: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip(str(record.get("path") or ""))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = str(record.get("name") or record.get("id") or "")
        top.addWidget(CText(name, size="md", weight="semibold"))
        top.addWidget(_Chip(f"v{record.get('version') or '?'}", accent=True))
        top.addWidget(
            _Chip(
                texts["enabled"] if record.get("enabled") else texts["disabled"],
                accent=bool(record.get("enabled")),
            )
        )
        top.addStretch(1)
        info.addLayout(top)
        info.addWidget(
            _ElidedLabel(f"{record.get('id')}  ·  {str(record.get('commit') or '')[:10]}", mono=True)
        )
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(_Chip(str(record.get("source") or "-")))
        for permission in list(record.get("permissions") or [])[:3]:
            chips.addWidget(_Chip(str(permission)))
        chips.addStretch(1)
        info.addLayout(chips)
        layout.addLayout(info, 1)

        actions = QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(6)
        plugin_id = str(record.get("id") or "")
        update = self._button(texts["update"], "primary", "solid", lambda: on_update(plugin_id))
        rollback = self._button(texts["rollback"], "secondary", "outlined", lambda: on_rollback(plugin_id))
        toggle = self._button(
            texts["disable"] if record.get("enabled") else texts["enable"],
            "warn",
            "outlined",
            lambda: on_toggle(plugin_id),
        )
        remove = self._button(texts["remove"], "danger", "text", lambda: on_remove(plugin_id))
        actions.addWidget(update, 0, 0)
        actions.addWidget(rollback, 0, 1)
        actions.addWidget(toggle, 1, 0)
        actions.addWidget(remove, 1, 1)
        layout.addLayout(actions)

    @staticmethod
    def _button(text: str, severity: str, variant: str, slot) -> CButton:
        button = CButton(text, size="sm", severity=severity, variant=variant, fixed_width=66)
        button.clicked.connect(slot)
        return button

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(
            painter,
            _card_rect(self),
            RADIUS,
            background=colors["hover"] if self._hovered else colors["background"],
            border=colors["border"],
        )
        painter.end()


class _ResultCard(QFrame):
    """发现：搜索结果卡片，直接安装。"""

    def __init__(
        self,
        record: dict[str, Any],
        install_text: str,
        permission_text: str,
        on_install: Callable[[dict[str, Any]], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(122)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = str(record.get("name") or record.get("id") or "")
        top.addWidget(CText(name, size="md", weight="semibold"))
        top.addWidget(_Chip(f"v{record.get('version') or '?'}", accent=True))
        top.addStretch(1)
        layout.addLayout(top)

        summary = str(record.get("summary") or record.get("id") or "")
        summary_label = CText(summary, size="sm", wrap=True)
        summary_label.setFixedHeight(34)
        layout.addWidget(summary_label)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addWidget(_Chip(str(record.get("source") or "-")))
        permissions = list(record.get("permissions") or [])
        if permissions:
            bottom.addWidget(_Chip(permission_text.format(count=len(permissions))))
        bottom.addStretch(1)
        install = CButton(install_text, size="sm", severity="success", fixed_width=64)
        install.clicked.connect(lambda: on_install(self.record))
        bottom.addWidget(install)
        layout.addLayout(bottom)

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(
            painter,
            _card_rect(self),
            RADIUS,
            background=colors["hover"] if self._hovered else colors["background"],
            border=_tint(colors["accent"], 90) if self._hovered else colors["border"],
        )
        painter.end()


class _SourceRow(QFrame):
    """来源：一行一个，信任级别用标签表达。"""

    def __init__(
        self,
        record: dict[str, Any],
        trust_texts: dict[str, str],
        remove_text: str,
        on_remove: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(62)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(12)
        trust = str(record.get("trust") or "user")
        layout.addWidget(_Chip(trust_texts.get(trust, trust), accent=trust == "official"))

        info = QVBoxLayout()
        info.setSpacing(3)
        info.addWidget(CText(str(record.get("id") or ""), size="sm", weight="semibold"))
        info.addWidget(_ElidedLabel(str(record.get("url") or ""), mono=True))
        layout.addLayout(info, 1)

        remove = CButton(remove_text, size="sm", severity="danger", variant="text", fixed_width=56)
        remove.clicked.connect(lambda: on_remove(str(record.get("id") or "")))
        layout.addWidget(remove)

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(
            painter,
            _card_rect(self),
            RADIUS,
            background=colors["hover"] if self._hovered else colors["background"],
            border=colors["border"],
        )
        painter.end()


class StorePage(QWidget):
    """插件管理：一页内完成安装、更新与来源维护。"""

    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        self._build()
        self.refresh_all()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 8)
        root.setSpacing(10)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 10, 12)
        column.setSpacing(20)

        column.addLayout(self._build_hero())
        column.addWidget(self._build_installed())
        column.addWidget(self._build_discover())
        column.addWidget(self._build_sources())
        column.addStretch(1)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

        self.status = CText(self.ctx.text("status.ready", "就绪"), size="sm")
        root.addWidget(self.status)
        self._set_status(self.ctx.text("status.ready", "就绪"))

    def _build_hero(self) -> QHBoxLayout:
        hero = QHBoxLayout()
        hero.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(CText(self.ctx.text("store.title", "插件管理"), size="xl", weight="semibold"))
        titles.addWidget(CText(self.ctx.text("store.subtitle", "已安装、发现与来源，在一页内完成"), size="sm"))
        hero.addLayout(titles, 1)

        self.stat_installed = _StatChip(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled = _StatChip(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources = _StatChip(self.ctx.text("stats.sources", "来源"))
        for chip in (self.stat_installed, self.stat_enabled, self.stat_sources):
            hero.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self.refresh_btn = CButton(
            self.ctx.text("store.refresh", "全部刷新"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        self.refresh_btn.clicked.connect(self.refresh_all)
        hero.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        return hero

    def _build_installed(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        header = _SectionHeader("01", self.ctx.text("sections.installed", "已安装"))
        layout.addWidget(header)
        self.installed_rows = QVBoxLayout()
        self.installed_rows.setSpacing(8)
        layout.addLayout(self.installed_rows)
        return host

    def _build_discover(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        header = _SectionHeader("02", self.ctx.text("sections.discover", "发现"))
        self.refresh_sources_btn = CButton(
            self.ctx.text("discover.refresh_sources", "刷新源"),
            size="sm",
            severity="secondary",
            variant="text",
        )
        self.refresh_sources_btn.clicked.connect(self._refresh_sources)
        header.add_action(self.refresh_sources_btn)
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.query = CInputText(placeholder=self.ctx.text("discover.placeholder", "搜索插件名称、ID 或简介…"))
        self.search_btn = CButton(self.ctx.text("discover.search", "搜索"), size="sm")
        self.search_btn.clicked.connect(self._run_search)
        self.query.returnPressed.connect(self._run_search)
        search_row.addWidget(self.query, 1)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        self.results_grid = QGridLayout()
        self.results_grid.setHorizontalSpacing(10)
        self.results_grid.setVerticalSpacing(10)
        self.results_grid.setColumnStretch(0, 1)
        self.results_grid.setColumnStretch(1, 1)
        layout.addLayout(self.results_grid)
        return host

    def _build_sources(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        header = _SectionHeader("03", self.ctx.text("sections.sources", "来源"))
        self.refresh_all_sources_btn = CButton(
            self.ctx.text("sources.refresh_all", "全部刷新"),
            size="sm",
            severity="secondary",
            variant="text",
        )
        self.refresh_all_sources_btn.clicked.connect(self._refresh_sources)
        header.add_action(self.refresh_all_sources_btn)
        layout.addWidget(header)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.source_url = CInputText(placeholder=self.ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_source_btn = CButton(self.ctx.text("sources.add", "添加"), size="sm")
        self.add_source_btn.clicked.connect(self._add_source)
        self.source_url.returnPressed.connect(self._add_source)
        add_row.addWidget(self.source_url, 1)
        add_row.addWidget(self.add_source_btn)
        layout.addLayout(add_row)

        self.source_rows = QVBoxLayout()
        self.source_rows.setSpacing(8)
        layout.addLayout(self.source_rows)
        return host

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    def refresh_all(self) -> None:
        self.installed = self._manager().installed_rows() if self._manager() is not None else []
        self.sources_list = self._sources().list() if self._sources() is not None else []
        self._rebuild_installed()
        self._rebuild_sources()
        self._run_search()
        self._refresh_stats()
        self._set_status(self.ctx.text("status.ready", "就绪"))

    def _refresh_stats(self) -> None:
        self.stat_installed.set_value(len(self.installed))
        self.stat_enabled.set_value(sum(1 for row in self.installed if row.get("enabled")))
        self.stat_sources.set_value(len(self.sources_list))

    def _rebuild_installed(self) -> None:
        _clear_layout(self.installed_rows)
        if not self.installed:
            self.installed_rows.addWidget(_EmptyCard(self.ctx.text("installed.empty", "还没有安装插件，去「发现」看看")))
            return
        texts = {
            "enabled": self.ctx.text("installed.enabled", "已启用"),
            "disabled": self.ctx.text("installed.disabled", "已停用"),
            "update": self.ctx.text("installed.update", "更新"),
            "rollback": self.ctx.text("installed.rollback", "回滚"),
            "enable": self.ctx.text("installed.enable", "启用"),
            "disable": self.ctx.text("installed.disable", "停用"),
            "remove": self.ctx.text("installed.remove", "卸载"),
        }
        for record in self.installed:
            self.installed_rows.addWidget(
                _PluginRow(
                    record,
                    texts,
                    self._update_plugin,
                    self._rollback_plugin,
                    self._toggle_plugin,
                    self._remove_plugin,
                )
            )

    def _run_search(self) -> None:
        _clear_layout(self.results_grid)
        self.results: list[dict[str, Any]] = []
        manager = self._manager()
        if manager is None:
            return
        installed = set(getattr(getattr(manager, "state", None), "plugins", {}) or {})
        seen: set[str] = set()
        for row in manager.search(self.query.text().strip()):
            plugin_id = str(row.get("id") or "")
            if not plugin_id or plugin_id in installed or plugin_id in seen:
                continue
            seen.add(plugin_id)
            self.results.append(row)
        if not self.results:
            grid_empty = _EmptyCard(self.ctx.text("discover.empty", "没有匹配的可安装插件"))
            self.results_grid.addWidget(grid_empty, 0, 0, 1, 2)
        for index, record in enumerate(self.results):
            card = _ResultCard(
                record,
                self.ctx.text("discover.install", "安装"),
                self.ctx.text("discover.permissions", "{count} 项权限"),
                self._install_plugin,
            )
            self.results_grid.addWidget(card, index // 2, index % 2)
        self.ctx.log(f"search plugins: {len(self.results)}")
        self.ctx.event("core_store.search", {"count": len(self.results)})

    def _rebuild_sources(self) -> None:
        _clear_layout(self.source_rows)
        if not self.sources_list:
            self.source_rows.addWidget(_EmptyCard(self.ctx.text("sources.empty", "还没有配置插件源")))
            return
        trust_texts = {
            "official": self.ctx.text("sources.official", "官方"),
            "user": self.ctx.text("sources.user", "用户"),
        }
        for record in self.sources_list:
            self.source_rows.addWidget(
                _SourceRow(
                    {
                        "id": record.source_id,
                        "url": record.url,
                        "trust": record.trust,
                    },
                    trust_texts,
                    self.ctx.text("sources.remove", "移除"),
                    self._remove_source,
                )
            )

    def _set_status(self, message: str, level: str = "info") -> None:
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

    def _finish(self, message: str, level: str = "info", *, reload: bool = True) -> None:
        self._set_status(message, level)
        QTimer.singleShot(0, self.refresh_all)
        if reload:
            self.schedule_reload()

    def schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            QTimer.singleShot(120, window.reload_plugins)

    # ------------------------------------------------------------------
    # 已安装操作
    # ------------------------------------------------------------------
    def _update_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        try:
            with self.ctx.timing("core_store.update"):
                result = manager.update(plugin_id)
            self.ctx.log(f"update: {result}")
            self.ctx.event("core_store.update", {"id": plugin_id, "version": result.get("version")})
            self._finish(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_UPDATE_FAILED", f"更新失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _rollback_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        try:
            with self.ctx.timing("core_store.rollback"):
                result = manager.rollback(plugin_id)
            self.ctx.log(f"rollback: {result}")
            self.ctx.event("core_store.rollback", {"id": plugin_id})
            self._finish(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_ROLLBACK_FAILED", f"回滚失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _toggle_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        row = next((item for item in self.installed if item.get("id") == plugin_id), None)
        if manager is None or row is None:
            return
        try:
            manager.set_enabled(plugin_id, not bool(row.get("enabled")))
            self._finish(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_TOGGLE_FAILED", f"切换失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _remove_plugin(self, plugin_id: str) -> None:
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text("confirm.remove", "确定卸载该插件？数据目录默认保留。"),
            severity="danger",
        )
        manager = self._manager()
        if not ok or manager is None:
            return
        try:
            manager.remove(plugin_id)
            self._finish(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_REMOVE_FAILED", f"卸载失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    # ------------------------------------------------------------------
    # 发现 / 来源
    # ------------------------------------------------------------------
    def _install_plugin(self, record: dict[str, Any]) -> None:
        plugin_id = str(record.get("id") or "")
        permissions = ", ".join(record.get("permissions") or []) or "-"
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("discover.install", "安装"),
            message=self.ctx.text("confirm.install", "安装 {id} v{version}？权限：{permissions}").format(
                id=plugin_id,
                version=record.get("version") or "?",
                permissions=permissions,
            ),
            severity="info",
        )
        manager = self._manager()
        if not ok or manager is None:
            return
        try:
            with self.ctx.timing("core_store.install"):
                result = manager.install(plugin_id, source_id=str(record.get("source") or ""))
            self.ctx.log(f"installed: {result}")
            self.ctx.event("core_store.install", {"id": plugin_id, "version": result.get("version")})
            self._finish(
                self.ctx.text("status.install_done", "已安装 {count} 个插件").format(count=1),
                "success",
            )
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_INSTALL_FAILED", f"安装失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self._set_status(self.ctx.text("status.refreshing", "正在刷新源…"))
        try:
            with self.ctx.timing("core_store.source_refresh"):
                sources.refresh_all()
            self.ctx.event("core_store.sources_refreshed")
            self._finish(self.ctx.text("status.refresh_done", "源刷新完成"), "success", reload=False)
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _add_source(self) -> None:
        sources = self._sources()
        url = self.source_url.text().strip()
        if sources is None or not url:
            return
        try:
            record = sources.add(url, refresh=True)
            self.ctx.event("core_store.source_added", {"id": record.source_id})
            self.source_url.setText("")
            self._finish(self.ctx.text("sources.added", "已添加源 {id}").format(id=record.source_id), "success", reload=False)
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_ADD_FAILED", f"添加源失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    def _remove_source(self, source_id: str) -> None:
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("sources.remove", "移除"),
            message=self.ctx.text("sources.confirm_remove", "移除源 {id}？已安装插件不受影响。").format(id=source_id),
            severity="warn",
        )
        sources = self._sources()
        if not ok or sources is None:
            return
        try:
            sources.remove(source_id)
            self.ctx.event("core_store.source_removed", {"id": source_id})
            self._finish(self.ctx.text("status.action_done", "操作完成"), "success", reload=False)
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_REMOVE_FAILED", f"移除源失败: {exc}", str(exc))
            self._finish(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error", reload=False)

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def _theme_changed(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.update()


__all__ = ["StorePage"]
