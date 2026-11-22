"""插件管理工作台：页签 + 主列表 + 内嵌检查器。

页面只通过鸭子类型读取窗口上的插件运行时，``guis`` 不 import ``gallery``；
没有运行时的宿主会得到只读的空页面，而不是报错。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.appcore import get_theme_manager
from sllkgui.guicore import (
    CButton,
    CChip,
    CConfirmDialog,
    CIconTile,
    CInputText,
    CSelectButton,
    run_task,
    single_shot,
)

from .context import PageContext
from .entries import (
    StoreRow,
    chip,
    empty_state,
    hero,
    label,
    meta_grid,
    permission_block,
    row_signature,
    section_title,
    version_chip,
)
from .panels import BusyStrip, InspectorPanel, ListPanel
from .theme import STAT_DIVIDER_OBJECT, page_sheet


def build_plugin_store_page(window) -> QWidget:
    """原生页面工厂：由窗口装配层在首次导航时调用。"""
    return StorePage(PageContext(lambda: window))


class _Stat(QWidget):
    """页头统计块：说明在上、数值在下，数值用等宽字体。"""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 0, 14, 0)
        column.setSpacing(1)
        self.caption = label("muted", caption, pixel_size=9)
        self.value = label("title", "0", pixel_size=17, weight="semibold", mono=True)
        column.addWidget(self.caption)
        column.addWidget(self.value)
        self.setMinimumWidth(70)

    def set_caption(self, text: str) -> None:
        self.caption.setText(text)

    def set_value(self, value: int | str) -> None:
        self.value.setText(str(value))


class _StatDivider(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName(STAT_DIVIDER_OBJECT)
        self.setFixedWidth(1)
        self.setFixedHeight(28)


class StorePage(QWidget):
    """插件管理工作台。"""

    #: 页签顺序与语言键（图标只用于对话/测试时的语义提示）
    _MODE_SPECS = (
        ("installed", "modes.installed", "已安装", "icon_store"),
        ("discover", "modes.discover", "发现", "icon_search"),
        ("sources", "modes.sources", "源", "icon_database"),
    )

    def __init__(self, ctx: PageContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.runtime = ctx.runtime()
        self.mode = "installed"
        self.query = ""
        self.add_source = False
        self._busy = False
        self._selection: dict[str, str] = {"installed": "", "discover": "", "sources": ""}
        self._counts = {"installed": 0, "discover": 0, "sources": 0}
        #: 文案版本：语言切换时递增，让行/详情按新文案重建一次
        self._view_revision = 0
        #: 当前详情的内容指纹与可原地更新的控件引用
        self._inspector_key: tuple[Any, ...] | None = None
        self._inspector_item_id = ""
        self._inspector_state_chip: CChip | None = None
        self._inspector_toggle_button: CButton | None = None
        self._inspector_enabled_state: bool | None = None
        self._inspector_buttons: list[tuple[CButton, bool]] = []
        self._inspector_history_host: QWidget | None = None
        self._inspector_history_layout: QVBoxLayout | None = None
        self._inspector_history_key: tuple[Any, ...] | None = None
        #: 当前列表空态对应的模式/搜索词，避免重复重建空态控件
        self._empty_list_key: tuple[Any, ...] | None = None
        #: 重建前的界面状态（由 :meth:`_restore_state` 填充）
        self._restore_mode = ""
        self._restore_scroll = 0
        self._build()
        self._restore_state()
        self._switch_mode(self._restore_mode or "installed", reset_query=False)
        self._apply_restored_scroll()
        self.refresh_stats()
        get_theme_manager().subscribe(self._theme_changed)

    def _apply_restored_scroll(self) -> None:
        """列表重建后把滚动条放回原位置（延迟到布局完成再设值）。"""
        if self._restore_scroll <= 0:
            return
        bar = self.list_panel.scroll.verticalScrollBar()
        value = self._restore_scroll
        single_shot(self, 0, lambda: bar.setValue(min(value, bar.maximum())))

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addLayout(self._build_toolbar())

        self.busy_strip = BusyStrip(self)
        root.addWidget(self.busy_strip)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.list_panel = ListPanel(self)
        self.inspector_panel = InspectorPanel(self)
        body.addWidget(self.list_panel)
        body.addWidget(self.inspector_panel, 1)
        root.addLayout(body, 1)

        self.setStyleSheet(page_sheet())

    def _build_header(self) -> QHBoxLayout:
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(16)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(2)
        self.eyebrow = label("muted", "SLLKGUI / PLUGINS", pixel_size=9, weight="medium")
        self.title_label = label("title", self.ctx.text("store.title", "插件管理"), pixel_size=18, weight="semibold")
        self.subtitle_label = label(
            "muted",
            self.ctx.text("store.subtitle", "已安装、发现与来源，在一处完成"),
            pixel_size=10,
        )
        titles.addWidget(self.eyebrow)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        hero_row.addLayout(titles, 1)

        stats = QHBoxLayout()
        # 与标题块的下沿对齐：上方留 12px，避免统计值贴住页头边缘。
        stats.setContentsMargins(0, 12, 0, 0)
        stats.setSpacing(0)
        self.stat_installed = _Stat(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled = _Stat(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources = _Stat(self.ctx.text("stats.sources", "来源"))
        for index, stat in enumerate((self.stat_installed, self.stat_enabled, self.stat_sources)):
            if index:
                stats.addWidget(_StatDivider(), 0, Qt.AlignmentFlag.AlignVCenter)
            stats.addWidget(stat, 0, Qt.AlignmentFlag.AlignTop)
        hero_row.addLayout(stats, 0)
        return hero_row

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)

        self.mode_tabs = CSelectButton(self._mode_labels(), index=0, size="sm")
        self.mode_tabs.setFixedWidth(330)
        self.mode_tabs.selectionChanged.connect(self._on_mode_index)
        toolbar.addWidget(self.mode_tabs)
        toolbar.addStretch(1)

        self.search = CInputText(placeholder=self.ctx.text("installed.filter", "过滤插件…"), icon="icon_search")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        self.search.returnPressed.connect(self._apply_search)
        toolbar.addWidget(self.search)

        self.refresh_button = CButton(
            self.ctx.text("action.refresh", "刷新"),
            icon="icon_refresh",
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        self.refresh_sources_button = CButton(
            self.ctx.text("action.refresh_sources", "刷新来源"),
            icon="icon_refresh",
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        self.add_source_button = CButton(
            self.ctx.text("action.add_source", "添加来源"),
            icon="icon_add",
            severity="primary",
            variant="solid",
            size="sm",
        )
        self.refresh_button.clicked.connect(self._refresh_installed)
        self.refresh_sources_button.clicked.connect(self._refresh_sources)
        self.add_source_button.clicked.connect(self._start_add_source)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.refresh_sources_button)
        toolbar.addWidget(self.add_source_button)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(160)
        self._search_timer.timeout.connect(self._apply_search)
        return toolbar

    # ------------------------------------------------------------------
    # 模式
    # ------------------------------------------------------------------
    def _mode_labels(self) -> list[str]:
        return [
            f"{self.ctx.text(key, caption)} {self._counts.get(mode, 0)}"
            for mode, key, caption, _icon in self._MODE_SPECS
        ]

    def _mode_index(self) -> int:
        for index, (mode, _key, _caption, _icon) in enumerate(self._MODE_SPECS):
            if mode == self.mode:
                return index
        return 0

    def _on_mode_index(self, index: int) -> None:
        if 0 <= index < len(self._MODE_SPECS):
            self.switch_mode(self._MODE_SPECS[index][0])

    def switch_mode(self, mode: str) -> None:
        self._switch_mode(mode, reset_query=True)

    def _switch_mode(self, mode: str, *, reset_query: bool) -> None:
        """切换页签；``reset_query=False`` 用于重建后恢复，保留用户搜索词。"""
        if mode not in {item[0] for item in self._MODE_SPECS}:
            return
        self.mode = mode
        self.add_source = False
        if reset_query:
            self.query = ""
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        elif self.query:
            # 恢复路径：把搜索框文字补回去（此时信号已断开，不会触发搜索）
            self.search.blockSignals(True)
            self.search.setText(self.query)
            self.search.blockSignals(False)
        self.search.setPlaceholderText(
            {
                "installed": self.ctx.text("installed.filter", "过滤插件…"),
                "discover": self.ctx.text("discover.placeholder", "搜索插件名称、简介或作者…"),
                "sources": self.ctx.text("sources.placeholder", "搜索来源…"),
            }[mode]
        )
        self.mode_tabs.set_index(self._mode_index(), emit=False)
        self._sync_actions()
        self._ensure_selection()
        self._refresh_list()
        self._refresh_inspector()
        self.refresh_stats()

    def _sync_actions(self) -> None:
        self.refresh_button.setVisible(self.mode == "installed")
        self.refresh_sources_button.setVisible(self.mode == "discover")
        self.add_source_button.setVisible(self.mode == "sources")

    # ------------------------------------------------------------------
    # 数据源（鸭子类型读取窗口运行时）
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    def _installed_rows(self) -> list[dict[str, Any]]:
        manager = self._manager()
        if manager is None:
            return []
        rows: list[dict[str, Any]] = []
        for item in manager.installed_rows():
            record = dict(item)
            record["installed"] = True
            rows.append(record)
        return rows

    def _discover_rows(self) -> list[dict[str, Any]]:
        manager = self._manager()
        if manager is None:
            return []
        needle = self.query.strip().lower()
        try:
            found = manager.search(needle)
        except Exception as exc:  # noqa: BLE001 - 源索引失败时页面保持可用
            self.ctx.log(f"读取插件索引失败: {exc}", "warning")
            return []
        installed = {str(row.get("id") or ""): row for row in self._installed_rows()}
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in found:
            record = dict(item)
            plugin_id = str(record.get("id") or "")
            if plugin_id in seen:
                continue
            seen.add(plugin_id)
            current = installed.get(plugin_id)
            record["installed"] = current is not None
            record["enabled"] = bool(current.get("enabled")) if current is not None else False
            record["installed_version"] = str(current.get("version") or "") if current is not None else ""
            source_version = str(record.get("version") or "")
            if current is not None and source_version and source_version != record["installed_version"]:
                record["update_available"] = True
                record["available_version"] = source_version
            rows.append(record)

        # 已安装但源索引暂时缺失的插件仍要出现在发现页，并标记「已安装」。
        for plugin_id, current in installed.items():
            if plugin_id in seen:
                continue
            name = str(current.get("name") or plugin_id)
            summary = str(current.get("summary") or "")
            if needle and needle not in f"{plugin_id} {name} {summary}".lower():
                continue
            rows.append(
                {
                    "id": plugin_id,
                    "name": name,
                    "summary": summary,
                    "version": str(current.get("version") or "?"),
                    "source": str(current.get("source") or ""),
                    "permissions": list(current.get("permissions") or []),
                    "compliance": current.get("compliance"),
                    "repository": str(current.get("repository") or ""),
                    "icon": str(current.get("icon") or ""),
                    "installed": True,
                    "enabled": bool(current.get("enabled")),
                    "installed_version": str(current.get("version") or ""),
                }
            )
        return rows

    def _source_rows(self) -> list[dict[str, Any]]:
        sources = self._sources()
        if sources is None:
            return []
        rows: list[dict[str, Any]] = []
        for record in sources.list():
            source_id = str(getattr(record, "source_id", "") or "")
            name = source_id
            try:
                info = sources.info(source_id)
                name = str(getattr(info, "name", "") or source_id)
            except Exception:  # noqa: BLE001 - 源清单缺失时回落到 id
                pass
            rows.append(
                {
                    "id": source_id,
                    "name": name,
                    "url": str(getattr(record, "url", "") or ""),
                    "trust": str(getattr(record, "trust", "user") or "user"),
                    "enabled": bool(getattr(record, "enabled", True)),
                    "commit": str(getattr(record, "commit", "") or ""),
                    "last_refresh": str(getattr(record, "last_refresh", "") or ""),
                }
            )
        return rows

    def _source_name(self, source_id: str) -> str:
        for row in self._source_rows():
            if row["id"] == source_id:
                return str(row["name"])
        return source_id or "—"

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------
    def refresh_stats(self) -> None:
        installed = self._installed_rows()
        sources = self._source_rows()
        discover = self._discover_rows()
        self._counts = {
            "installed": len(installed),
            "discover": len(discover),
            "sources": len(sources),
        }
        self.stat_installed.set_value(len(installed))
        self.stat_enabled.set_value(sum(1 for row in installed if row.get("enabled")))
        self.stat_sources.set_value(len(sources))
        self.mode_tabs.set_options(self._mode_labels(), index=self._mode_index(), emit=False)

    def refresh_all(self) -> None:
        self._ensure_selection()
        self._refresh_list()
        self._refresh_inspector()
        self.refresh_stats()

    def _ensure_selection(self) -> None:
        if self._selection.get(self.mode):
            return
        rows = self._current_rows()
        if rows:
            self._selection[self.mode] = str(rows[0].get("id") or "")

    def _current_rows(self) -> list[dict[str, Any]]:
        needle = self.query.strip().lower()
        if self.mode == "installed":
            rows = self._installed_rows()
            if needle:
                rows = [
                    row for row in rows if needle in f"{row.get('id')} {row.get('name')} {row.get('source')}".lower()
                ]
            return rows
        if self.mode == "discover":
            return self._discover_rows()
        rows = self._source_rows()
        if needle:
            rows = [row for row in rows if needle in f"{row.get('id')} {row.get('name')} {row.get('url')}".lower()]
        return rows

    def _refresh_list(self) -> None:
        rows = self._current_rows()
        title = self.ctx.text(
            f"list.title.{self.mode}",
            {"installed": "已安装插件", "discover": "可发现的插件", "sources": "插件源"}[self.mode],
        )
        meta_key = f"list.meta.{self.mode}"
        if self.mode == "installed":
            meta = self.ctx.text(meta_key, "共 {count} 个").format(count=len(rows))
        elif self.mode == "discover":
            meta = self.ctx.text(meta_key, "共 {count} 个结果").format(count=len(rows))
        else:
            meta = self.ctx.text(meta_key, "共 {count} 个来源").format(count=len(rows))
        self.list_panel.set_titles(title, meta)

        if not rows:
            empty_key = (self.mode, self.query.strip(), self._view_revision)
            if empty_key != self._empty_list_key:
                self.list_panel.set_empty(self._empty_widget())
                self._empty_list_key = empty_key
            self.list_panel.set_busy(self._busy)
            return
        self._empty_list_key = None

        existing = {str(row.record.get("id") or ""): row for row in self.list_panel.rows()}
        widgets: list[StoreRow] = []
        for record in rows:
            record_id = str(record.get("id") or "")
            signature = row_signature(record, self.mode)
            row = existing.get(record_id)
            if row is not None and row.signature == signature and row.view_revision == self._view_revision:
                # 行内视觉未变：只同步数据与开关，保留控件身份与滚动位置。
                row.sync_record(record)
            else:
                # 只替换受影响的那一行，其余行继续复用。
                row = self._create_row(record, signature)
            widgets.append(row)
        self.list_panel.sync_rows(widgets)
        self.list_panel.set_selected(self._selection.get(self.mode, ""))
        self.list_panel.set_busy(self._busy)

    def _create_row(self, record: dict[str, Any], signature: tuple[Any, ...]) -> StoreRow:
        row = StoreRow(record, self.mode, self.ctx, self.list_panel)
        row.signature = signature
        row.view_revision = self._view_revision
        row.clicked.connect(self._on_row_clicked)
        row.toggled.connect(self._on_row_toggled)
        row.install_requested.connect(self._install_plugin)
        return row

    def _empty_widget(self) -> QWidget:
        if self.query.strip():
            title_key = "list.no_match_source_title" if self.mode == "sources" else "list.no_match_title"
            return empty_state(
                "icon_search",
                self.ctx.text(title_key, "没有匹配的插件"),
                self.ctx.text("list.no_match_hint", "没有找到与「{query}」匹配的结果。").format(
                    query=self.query.strip()
                ),
                self.ctx.text("list.clear_search", "清除搜索"),
                self._clear_search,
            )
        if self.mode == "installed":
            return empty_state(
                "icon_store",
                self.ctx.text("installed.empty_title", "还没有安装插件"),
                self.ctx.text("installed.empty_hint", "从「发现」里挑一个插件，安装后就能在这里启停与更新。"),
                self.ctx.text("action.go_discover", "去发现看看"),
                lambda: self.switch_mode("discover"),
            )
        if self.mode == "discover":
            return empty_state(
                "icon_store",
                self.ctx.text("discover.empty_title", "没有可发现的插件"),
                self.ctx.text("discover.empty_hint", "添加或启用一个插件源，再回来看看。"),
            )
        return empty_state(
            "icon_database",
            self.ctx.text("sources.empty_title", "还没有配置插件源"),
            self.ctx.text("sources.empty_hint", "添加一个 Git 仓库地址，就能发现并安装社区插件。"),
            self.ctx.text("action.add_source", "添加来源"),
            self._start_add_source,
        )

    # ------------------------------------------------------------------
    # 检查器
    # ------------------------------------------------------------------
    def _refresh_inspector(self) -> None:
        if self.mode == "sources" and self.add_source:
            self.inspector_panel.set_titles(self.ctx.text("inspector.add_source_title", "添加来源"), "")
            key = ("add_source", self._view_revision)
            if key != self._inspector_key:
                self._inspector_item_id = ""
                self._reset_inspector_refs()
                self.inspector_panel.set_content(self._build_add_source())
                self._inspector_key = key
            return

        record = self._selected_record()
        if record is None:
            if self.mode == "sources":
                title = self.ctx.text("inspector.empty_source_title", "选择一个来源")
                hint = self.ctx.text(
                    "inspector.empty_source_hint", "在左侧选择来源，右侧会显示地址、信任级别与刷新操作。"
                )
                icon = "icon_database"
            else:
                title = self.ctx.text("inspector.empty_title", "选择一个插件")
                hint = self.ctx.text("inspector.empty_hint", "在左侧选择插件，右侧会显示版本、权限与可用操作。")
                icon = "icon_store"
            self.inspector_panel.set_titles(self.ctx.text("inspector.title", "详情"), "")
            key = ("empty", self.mode, self._view_revision)
            if key != self._inspector_key:
                self._inspector_item_id = ""
                self._reset_inspector_refs()
                self.inspector_panel.set_content(empty_state(icon, title, hint))
                self._inspector_key = key
            return

        if self.mode == "sources":
            self.inspector_panel.set_titles(self.ctx.text("inspector.title", "详情"), "")
            self._sync_selected_inspector(
                ("source", self._view_revision, self._freeze_record(record)),
                record,
                self._build_source_inspector,
            )
            return

        source_id = str(record.get("source") or "")
        self.inspector_panel.set_titles(
            self.ctx.text("inspector.title", "详情"),
            self._source_name(source_id) if source_id else "",
        )
        self._sync_selected_inspector(
            ("plugin", self._view_revision, self._freeze_record(record)),
            record,
            self._build_plugin_inspector,
        )

    def _sync_selected_inspector(
        self,
        key: tuple[Any, ...],
        record: dict[str, Any],
        builder: Callable[[dict[str, Any]], QWidget],
    ) -> None:
        """内容指纹未变时只同步启停态与重载历史；变化时才替换详情内容。"""
        item_id = str(record.get("id") or "")
        if key == self._inspector_key:
            self._sync_inspector_enabled(bool(record.get("enabled", True)))
            if self.mode != "sources":
                self._sync_inspector_history(item_id)
            return
        self._reset_inspector_refs()
        self.inspector_panel.set_content(builder(record))
        self._inspector_key = key
        self._inspector_item_id = item_id
        self._sync_inspector_enabled(bool(record.get("enabled", True)))
        self._apply_busy_to_inspector()

    @classmethod
    def _freeze_record(cls, record: dict[str, Any]) -> tuple[Any, ...]:
        """把详情数据压成可比较的指纹；``enabled`` 由局部更新处理，故排除。"""
        return tuple(sorted((str(key), cls._freeze(value)) for key, value in record.items() if key != "enabled"))

    @classmethod
    def _freeze(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((str(key), cls._freeze(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(cls._freeze(item) for item in value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    def _selected_record(self) -> dict[str, Any] | None:
        selected = str(self._selection.get(self.mode) or "")
        if not selected:
            return None
        if self.mode == "installed":
            rows = self._installed_rows()
        elif self.mode == "discover":
            rows = self._discover_rows()
        else:
            rows = self._source_rows()
        return next((row for row in rows if str(row.get("id") or "") == selected), None)

    def _action_button(
        self,
        text: str,
        *,
        severity: str,
        variant: str,
        icon: str,
        callback: Callable[[], None],
        enabled: bool = True,
        tooltip: str = "",
    ) -> CButton:
        button = CButton(text, icon=icon, severity=severity, variant=variant, size="sm")
        button.setEnabled(enabled and not self._busy)
        if tooltip:
            button.setToolTip(tooltip)
        button.clicked.connect(callback)
        # 记录「空闲时是否可用」，忙碌态变化时只改按钮状态，不重建详情。
        self._inspector_buttons.append((button, bool(enabled)))
        return button

    def _build_plugin_inspector(self, record: dict[str, Any]) -> QWidget:
        installed = bool(record.get("installed"))
        enabled = bool(record.get("enabled"))
        version = str(record.get("installed_version") or record.get("version") or "?")
        plugin_id = str(record.get("id") or "")
        self._reset_inspector_refs()

        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        chips = [version_chip(f"v{version}")]
        state_chip = (
            chip(
                self.ctx.text("installed.enabled", "已启用")
                if enabled
                else self.ctx.text("installed.disabled", "已停用"),
                accent=enabled,
            )
            if installed
            else chip(self.ctx.text("detail.not_installed", "未安装"))
        )
        chips.append(state_chip)
        if installed:
            self._inspector_state_chip = state_chip
        if record.get("update_available"):
            chips.append(
                chip(
                    f"{self.ctx.text('detail.available', '可用版本')} v{record.get('available_version') or ''}",
                )
            )
        column.addWidget(
            hero(
                record,
                chips,
                icon_name="icon_store",
                icon_file=str(record.get("icon") or ""),
            )
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        if installed:
            previous = record.get("previous") or {}
            has_previous = isinstance(previous, dict) and bool(previous.get("version"))
            actions.addWidget(
                self._action_button(
                    self.ctx.text("installed.remove", "卸载"),
                    severity="danger",
                    variant="outlined",
                    icon="icon_trash",
                    callback=lambda: self._remove_plugin(plugin_id),
                )
            )
            toggle = self._action_button(
                self.ctx.text("installed.disable", "停用") if enabled else self.ctx.text("installed.enable", "启用"),
                severity="warn",
                variant="outlined",
                icon="icon_close" if enabled else "icon_check",
                callback=lambda: self._toggle_plugin(plugin_id),
            )
            self._inspector_toggle_button = toggle
            actions.addWidget(toggle)
            actions.addWidget(
                self._action_button(
                    self.ctx.text("installed.rollback", "回滚"),
                    severity="secondary",
                    variant="outlined",
                    icon="icon_restore",
                    callback=lambda: self._rollback_plugin(plugin_id),
                    enabled=has_previous,
                    tooltip="" if has_previous else self.ctx.text("inspector.no_previous", "没有可回滚的版本"),
                )
            )
            actions.addWidget(
                self._action_button(
                    self.ctx.text("installed.update", "更新"),
                    severity="primary",
                    variant="solid",
                    icon="icon_refresh",
                    callback=lambda: self._update_plugin(plugin_id),
                )
            )
        else:
            actions.addWidget(
                self._action_button(
                    self.ctx.text("discover.install", "安装"),
                    severity="primary",
                    variant="solid",
                    icon="icon_add",
                    callback=lambda: self._install_plugin(record),
                )
            )
        actions.addStretch(1)
        column.addLayout(actions)

        column.addWidget(section_title(self.ctx.text("detail.about", "简介")))
        summary = str(record.get("summary") or self.ctx.text("detail.no_description", "暂无简介"))
        column.addWidget(label("muted", summary, pixel_size=10, wrap=True))

        column.addWidget(section_title(self.ctx.text("detail.meta", "基础信息")))
        items: list[tuple[str, str, bool]] = [
            (self.ctx.text("installed.version", "版本"), f"v{version}", True),
        ]
        if record.get("update_available"):
            items.append(
                (
                    self.ctx.text("detail.available", "可用版本"),
                    f"v{record.get('available_version') or ''}",
                    True,
                )
            )
        source_id = str(record.get("source") or "")
        if source_id:
            items.append((self.ctx.text("installed.source", "来源"), self._source_name(source_id), False))
        commit = str(record.get("commit") or "")
        if commit:
            items.append((self.ctx.text("installed.commit", "提交"), commit[:12], True))
        path = str(record.get("path") or "")
        if path and installed:
            items.append((self.ctx.text("installed.path", "目录"), path, True))
        previous = record.get("previous") or {}
        if isinstance(previous, dict) and previous.get("version"):
            items.append((self.ctx.text("detail.previous", "上一版本"), f"v{previous.get('version')}", True))
        compliance = record.get("compliance")
        if compliance == 1:
            items.append(
                (
                    self.ctx.text("detail.compliance", "合规级别"),
                    self.ctx.text("compliance.verified", "已校验"),
                    False,
                )
            )
        author = str(record.get("author") or "")
        if author:
            items.append((self.ctx.text("detail.author", "作者"), author, False))
        categories = record.get("categories") or []
        if categories:
            items.append(
                (
                    self.ctx.text("detail.categories", "分类"),
                    " / ".join(str(item) for item in categories),
                    False,
                )
            )
        repository = str(record.get("repository") or "")
        if repository:
            items.append((self.ctx.text("detail.repository", "仓库"), repository, True))
        column.addWidget(meta_grid(items))

        column.addWidget(permission_block(list(record.get("permissions") or []), self.ctx))

        # 最近重载单独放在一个宿主里：重载完成后只更新这一小块。
        history_host = QWidget()
        history_layout = QVBoxLayout(history_host)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(12)
        self._inspector_history_host = history_host
        self._inspector_history_layout = history_layout
        column.addWidget(history_host)
        self._fill_inspector_history(plugin_id)

        column.addStretch(1)
        return content

    def _reload_history_rows(self, plugin_id: str) -> list[tuple[str, str, bool]]:
        history = getattr(self.runtime, "recent_reloads", None)
        if not callable(history):
            return []
        rows: list[tuple[str, str, bool]] = []
        try:
            entries = history(8)
        except Exception:  # noqa: BLE001 - 诊断信息缺失不影响详情展示
            return []
        for item in entries:
            if plugin_id not in list(getattr(item, "targets", []) or []):
                continue
            status = (
                self.ctx.text("detail.reload_ok", "成功")
                if getattr(item, "ok", False)
                else str(getattr(item, "code", "") or self.ctx.text("detail.reload_failed", "失败"))
            )
            duration = float(getattr(item, "duration_ms", 0.0) or 0.0)
            rollback = str(getattr(item, "rollback", "none") or "none")
            rows.append((status, f"{duration:.0f} ms · rollback={rollback}", True))
        return rows

    def _fill_inspector_history(self, plugin_id: str) -> None:
        """重填「最近重载」区块；内容未变时保持原控件。"""
        layout = self._inspector_history_layout
        host = self._inspector_history_host
        if layout is None or host is None:
            return
        rows = self._reload_history_rows(plugin_id)
        key = tuple(rows)
        if key == self._inspector_history_key:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if rows:
            layout.addWidget(section_title(self.ctx.text("detail.reload_history", "最近重载")))
            layout.addWidget(meta_grid(rows[:3]))
        host.setVisible(bool(rows))
        self._inspector_history_key = key

    def _sync_inspector_history(self, plugin_id: str) -> None:
        if str(self._inspector_item_id or "") != str(plugin_id or ""):
            return
        try:
            self._fill_inspector_history(plugin_id)
        except RuntimeError:  # 详情已随页面销毁
            self._inspector_history_host = None
            self._inspector_history_layout = None

    def _build_source_inspector(self, record: dict[str, Any]) -> QWidget:
        trust = str(record.get("trust") or "user")
        official = trust == "official"
        enabled = bool(record.get("enabled"))
        source_id = str(record.get("id") or "")
        self._reset_inspector_refs()

        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        state_chip = chip(
            self.ctx.text("installed.enabled", "已启用") if enabled else self.ctx.text("installed.disabled", "已停用"),
            accent=enabled,
        )
        self._inspector_state_chip = state_chip
        chips = [
            chip(
                self.ctx.text("sources.official", "官方") if official else self.ctx.text("sources.user", "用户"),
                accent=official,
            ),
            state_chip,
        ]
        column.addWidget(hero(record, chips, icon_name="icon_database"))

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(
            self._action_button(
                self.ctx.text("sources.remove", "移除"),
                severity="danger",
                variant="outlined",
                icon="icon_trash",
                callback=lambda: self._remove_source(source_id),
            )
        )
        actions.addWidget(
            self._action_button(
                self.ctx.text("sources.refresh", "刷新"),
                severity="primary",
                variant="solid",
                icon="icon_refresh",
                callback=lambda: self._refresh_source(source_id),
            )
        )
        actions.addStretch(1)
        column.addLayout(actions)

        column.addWidget(section_title(self.ctx.text("detail.meta", "基础信息")))
        column.addWidget(
            meta_grid(
                [
                    (self.ctx.text("detail.source_id", "源 ID"), source_id, True),
                    (self.ctx.text("detail.url", "地址"), str(record.get("url") or ""), True),
                    (
                        self.ctx.text("detail.trust", "信任级别"),
                        self.ctx.text("sources.official", "官方")
                        if official
                        else self.ctx.text("sources.user", "用户"),
                        False,
                    ),
                    (
                        self.ctx.text("detail.status", "状态"),
                        self.ctx.text("installed.enabled", "已启用")
                        if enabled
                        else self.ctx.text("installed.disabled", "已停用"),
                        False,
                    ),
                    (self.ctx.text("installed.commit", "提交"), str(record.get("commit") or "-")[:12], True),
                    (self.ctx.text("detail.last_refresh", "最近刷新"), str(record.get("last_refresh") or "-"), False),
                ]
            )
        )
        column.addStretch(1)
        return content

    def _build_add_source(self) -> QWidget:
        self._reset_inspector_refs()
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        header.addWidget(CIconTile("icon_database", 48, content), 0, Qt.AlignmentFlag.AlignTop)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(
            label("title", self.ctx.text("inspector.add_source_title", "添加来源"), pixel_size=17, weight="semibold")
        )
        text_column.addWidget(
            label(
                "muted",
                self.ctx.text("inspector.add_source_hint", "支持 Git 仓库地址；添加后会自动刷新索引。"),
                pixel_size=10,
                wrap=True,
            )
        )
        header.addLayout(text_column, 1)
        column.addLayout(header)

        column.addWidget(section_title(self.ctx.text("inspector.url", "地址")))
        self._source_url = CInputText(
            placeholder=self.ctx.text("inspector.url_placeholder", "https://example.com/plugins.git")
        )
        self._source_url.returnPressed.connect(self._submit_source)
        column.addWidget(self._source_url)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        add_button = CButton(
            self.ctx.text("action.add_source", "添加来源"),
            icon="icon_add",
            severity="primary",
            variant="solid",
            size="sm",
        )
        add_button.setEnabled(not self._busy)
        add_button.clicked.connect(self._submit_source)
        self._inspector_buttons.append((add_button, True))
        cancel = CButton(
            self.ctx.text("action.cancel", "取消"),
            severity="secondary",
            variant="text",
            size="sm",
        )
        cancel.clicked.connect(self._cancel_add_source)
        actions.addWidget(add_button)
        actions.addWidget(cancel)
        actions.addStretch(1)
        column.addLayout(actions)
        column.addStretch(1)
        return content

    # ------------------------------------------------------------------
    # 列表交互
    # ------------------------------------------------------------------
    def _on_row_clicked(self, record: dict[str, Any]) -> None:
        self.add_source = False
        self._selection[self.mode] = str(record.get("id") or "")
        self.list_panel.set_selected(self._selection[self.mode])
        self._refresh_inspector()

    def _on_row_toggled(self, item_id: str, enabled: bool) -> None:
        if self.mode == "sources":
            self._set_source_enabled(item_id, enabled)
        else:
            self._set_plugin_enabled(item_id, enabled)

    def _apply_search(self) -> None:
        self.query = self.search.text().strip()
        self._refresh_list()
        self.refresh_stats()

    def _clear_search(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.query = ""
        self._refresh_list()
        self.refresh_stats()

    # ------------------------------------------------------------------
    # 忙碌 / 提示
    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        if busy:
            self.busy_strip.start(text)
        else:
            self.busy_strip.stop()
        self.list_panel.set_busy(busy)
        for button in (self.refresh_button, self.refresh_sources_button, self.add_source_button):
            button.setEnabled(not busy)
        # 忙碌只改变按钮可用性，详情内容与滚动位置保持不变。
        self._apply_busy_to_inspector()

    # ------------------------------------------------------------------
    # 详情局部同步
    # ------------------------------------------------------------------
    def _reset_inspector_refs(self) -> None:
        self._inspector_buttons = []
        self._inspector_state_chip = None
        self._inspector_toggle_button = None
        self._inspector_enabled_state = None
        self._inspector_history_host = None
        self._inspector_history_layout = None
        self._inspector_history_key = None

    def _apply_busy_to_inspector(self) -> None:
        for button, idle_enabled in self._inspector_buttons:
            try:
                button.setEnabled(bool(idle_enabled) and not self._busy)
            except RuntimeError:  # 按钮已随旧详情销毁
                continue

    def _sync_inspector_enabled(self, enabled: bool) -> None:
        """只更新详情里的状态片与启停按钮，不重建详情。"""
        enabled = bool(enabled)
        if self._inspector_enabled_state == enabled:
            return
        self._inspector_enabled_state = enabled
        state_chip = self._inspector_state_chip
        if state_chip is not None:
            try:
                text = (
                    self.ctx.text("installed.enabled", "已启用")
                    if enabled
                    else self.ctx.text("installed.disabled", "已停用")
                )
                if state_chip.text() != text:
                    state_chip.set_text(text)
                state_chip.set_tone("accent" if enabled else "neutral")
            except RuntimeError:
                self._inspector_state_chip = None
        toggle = self._inspector_toggle_button
        if toggle is not None:
            try:
                text = (
                    self.ctx.text("installed.disable", "停用") if enabled else self.ctx.text("installed.enable", "启用")
                )
                if toggle.text() != text:
                    toggle.setText(text)
                toggle.set_icon("icon_close" if enabled else "icon_check")
            except RuntimeError:
                self._inspector_toggle_button = None

    def _sync_item_state(self, item_id: str, enabled: bool) -> None:
        """同步某个插件/来源的启停态：目标行开关 + 当前详情状态片。"""
        for row in self.list_panel.rows():
            if str(row.record.get("id") or "") == str(item_id):
                row.set_enabled_state(enabled)
                break
        if str(self._inspector_item_id or "") == str(item_id):
            self._sync_inspector_enabled(enabled)

    def _plugin_enabled(self, plugin_id: str) -> bool | None:
        """读取插件的真实启停态；读取失败返回 ``None``。"""
        manager = self._manager()
        if manager is None:
            return None
        try:
            for row in manager.installed_rows():
                if str(row.get("id") or "") == str(plugin_id):
                    return bool(row.get("enabled"))
        except Exception:  # noqa: BLE001 - 读不到时保持界面现状
            return None
        return None

    def _toggle_plugin(self, plugin_id: str) -> None:
        record = self._selected_record()
        enabled = bool(record.get("enabled")) if record is not None else False
        self._set_plugin_enabled(plugin_id, not enabled)

    def set_status(self, message: str, level: str = "info") -> None:
        """页内状态提示：统一走 toast 总线（``base.plugin_store`` 通道）。"""
        if not message:
            return
        self._toast(message, level)

    def _toast(
        self,
        message: str,
        level: str = "info",
        *,
        code: str = "",
        detail: str = "",
    ) -> None:
        """发一条基座 toast；失败只记日志，不影响页面流程。"""
        from sllkgui.appcore.feedback import (
            ToastAction,
            ToastAnchor,
            ToastMode,
            ToastRequest,
            normalize_level,
        )
        from sllkgui.guicore.feedback import toast_bus

        actions: tuple[ToastAction, ...] = ()
        on_action = None
        if code:
            label = str(self.ctx.text("status.copy_error", "复制错误信息"))
            actions = (ToastAction("copy-error", label),)
            on_action = lambda _action_id: self._copy_error(code, message, detail)  # noqa: E731
        try:
            toast_bus().show(
                ToastAnchor.AUTO,
                ToastRequest(
                    text=message,
                    title=self.ctx.text("store.title", "插件管理"),
                    level=normalize_level(level)[0],
                    detail=detail,
                    code=code,
                    scope="base",
                    channel="base.plugin_store",
                    mode=ToastMode.REPLACE,
                    dedupe_key=f"plugin_store.{code}" if code else "",
                    actions=actions,
                    on_action=on_action,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - 提示失败不得打断插件管理操作
            self.ctx.log(f"toast 显示失败: {exc}", "warning")

    def _copy_error(self, code: str, message: str, detail: str) -> None:
        from PySide6.QtWidgets import QApplication

        text = f"{code}: {message}"
        if detail:
            text = f"{text}\n{detail}"
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.ctx.log(f"错误信息已复制: {code}", "debug")

    def _fail(self, code: str, message: str, exc: Exception) -> None:
        from .copy import failure_copy

        self.ctx.report_error(code, message, str(exc))
        text, level = failure_copy(self.ctx, code)
        self._toast(text, level, code=code, detail=f"{message}\n{exc}")

    def _run_async(
        self,
        *,
        name: str,
        fn: Callable[[], Any],
        busy_text: str,
        success_message: Callable[[Any], str] | None,
        error_code: str,
        on_done: Callable[[Any], None] | None = None,
        reload_plugins: bool = False,
    ) -> None:
        """后台执行 git / 文件操作；页面保持可见，只禁用会产生冲突的动作。"""
        if self._busy:
            return
        self._set_busy(True, busy_text)

        def finish() -> None:
            self._set_busy(False)

        def done(result: Any) -> None:
            finish()
            if on_done is not None:
                on_done(result)
            elif success_message is not None:
                self.set_status(success_message(result), "success")
            single_shot(self, 0, self.refresh_all)
            if reload_plugins:
                self.schedule_reload()

        def failed(error: str) -> None:
            finish()
            self._fail(error_code, f"{name} failed: {error}", RuntimeError(error))
            single_shot(self, 0, self.refresh_all)

        try:
            run_task(self, lambda _emit: fn(), on_done=done, on_error=failed, name=name)
        except Exception as exc:  # noqa: BLE001 - 任务启动失败不能让页面停在忙碌态
            failed(str(exc))

    # ------------------------------------------------------------------
    # 插件动作
    # ------------------------------------------------------------------
    def _set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        if self._busy:
            return
        manager = self._manager()
        if manager is None:
            return
        try:
            result = manager.set_enabled(plugin_id, enabled) or {}
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self._fail("PLUGIN_STORE_TOGGLE_FAILED", f"切换插件状态失败: {exc}", exc)
            # 失败时把开关拨回真实状态，不刷新整页。
            actual = self._plugin_enabled(plugin_id)
            self._sync_item_state(plugin_id, not enabled if actual is None else actual)
            return

        self._sync_item_state(plugin_id, enabled)
        for dependent in result.get("disabled_dependents") or []:
            self._sync_item_state(str(dependent), False)
        self.refresh_stats()
        name = self._name_of_plugin(plugin_id)
        message = (
            self.ctx.text("status.enabled_done", "已启用「{name}」").format(name=name)
            if enabled
            else self.ctx.text("status.disabled_done", "已停用「{name}」").format(name=name)
        )
        dependents = list(result.get("disabled_dependents") or [])
        if dependents:
            message += self.ctx.text(
                "status.dependents_disabled",
                "（同时停用 {count} 个依赖插件）",
            ).format(count=len(dependents))
        self.set_status(message, "success")
        self._reload_one(plugin_id, "enable" if enabled else "disable", load=enabled)

    def _update_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        name = self._name_of_plugin(plugin_id)

        def done(result: dict[str, Any]) -> None:
            if result.get("updated"):
                message = self.ctx.text("status.update_done", "「{name}」已更新到 v{version}").format(
                    name=name,
                    version=result.get("version") or "",
                )
            else:
                message = self.ctx.text("status.up_to_date", "「{name}」已是最新版本").format(name=name)
            self.set_status(message, "success")
            self._reload_one(plugin_id, "update")

        self._run_async(
            name="plugin_store.update",
            fn=lambda: manager.update(plugin_id, hot_reload=True),
            busy_text=self.ctx.text("status.updating", "正在更新插件…"),
            success_message=None,
            error_code="PLUGIN_STORE_UPDATE_FAILED",
            on_done=done,
        )

    def _rollback_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        name = self._name_of_plugin(plugin_id)

        def done(result: dict[str, Any]) -> None:
            self.set_status(
                self.ctx.text("status.rollback_done", "「{name}」已回滚到 v{version}").format(
                    name=name,
                    version=result.get("version") or "",
                ),
                "success",
            )
            self._reload_one(plugin_id, "rollback")

        self._run_async(
            name="plugin_store.rollback",
            fn=lambda: manager.rollback(plugin_id, hot_reload=True),
            busy_text=self.ctx.text("status.rolling_back", "正在回滚插件…"),
            success_message=None,
            error_code="PLUGIN_STORE_ROLLBACK_FAILED",
            on_done=done,
        )

    def _remove_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None or self._busy:
            return
        name = self._name_of_plugin(plugin_id)
        ok = CConfirmDialog.ask(
            self.ctx.parent_window() or self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text(
                "confirm.remove",
                "确定卸载「{name}」？插件的设置与数据目录会保留。",
            ).format(name=name),
            severity="danger",
        )
        if not ok:
            return

        def done(_result: Any) -> None:
            if self._selection.get("installed") == plugin_id:
                self._selection["installed"] = ""
            self.set_status(self.ctx.text("status.remove_done", "已卸载「{name}」").format(name=name), "success")
            self._reload_one(plugin_id, "remove", load=False)

        self._run_async(
            name="plugin_store.remove",
            fn=lambda: manager.remove(plugin_id),
            busy_text=self.ctx.text("status.removing", "正在卸载插件…"),
            success_message=None,
            error_code="PLUGIN_STORE_REMOVE_FAILED",
            on_done=done,
        )

    def _install_plugin(self, record: dict[str, Any]) -> None:
        manager = self._manager()
        if manager is None or self._busy:
            return
        plugin_id = str(record.get("id") or "")
        name = str(record.get("name") or plugin_id)

        def done(_result: Any) -> None:
            self._selection["installed"] = plugin_id
            self.set_status(self.ctx.text("status.install_done", "已安装「{name}」").format(name=name), "success")
            self._reload_one(plugin_id, "install")

        self._run_async(
            name="plugin_store.install",
            fn=lambda: manager.install(plugin_id, source_id=str(record.get("source") or "")),
            busy_text=self.ctx.text("status.installing", "正在安装插件…"),
            success_message=None,
            error_code="PLUGIN_STORE_INSTALL_FAILED",
            on_done=done,
        )

    def _name_of_plugin(self, plugin_id: str) -> str:
        for row in self._installed_rows():
            if str(row.get("id") or "") == plugin_id:
                return str(row.get("name") or plugin_id)
        for row in self._discover_rows():
            if str(row.get("id") or "") == plugin_id:
                return str(row.get("name") or plugin_id)
        return plugin_id

    # ------------------------------------------------------------------
    # 源动作
    # ------------------------------------------------------------------
    def _start_add_source(self) -> None:
        if self._busy:
            return
        self.add_source = True
        self._refresh_inspector()

    def _cancel_add_source(self) -> None:
        self.add_source = False
        self._refresh_inspector()

    def _submit_source(self) -> None:
        input_widget = getattr(self, "_source_url", None)
        try:
            url = input_widget.text().strip() if input_widget is not None else ""
        except RuntimeError:  # 检查器已重建，旧输入框随父级销毁
            url = ""
        if not url:
            self.set_status(self.ctx.text("sources.url_required", "请输入仓库地址。"), "warning")
            return
        self._add_source(url)

    def _add_source(self, url: str) -> None:
        sources = self._sources()
        if sources is None or self._busy:
            return

        def done(record: Any) -> None:
            self.add_source = False
            self._selection["sources"] = str(getattr(record, "source_id", "") or "")
            self.set_status(self.ctx.text("sources.added", "已添加来源。"), "success")

        self._run_async(
            name="plugin_store.source_add",
            fn=lambda: sources.add(url, refresh=True),
            busy_text=self.ctx.text("status.adding_source", "正在添加来源…"),
            success_message=None,
            error_code="PLUGIN_STORE_SOURCE_ADD_FAILED",
            on_done=done,
        )

    def _refresh_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None:
            return
        self._run_async(
            name="plugin_store.source_refresh",
            fn=lambda: sources.refresh(source_id),
            busy_text=self.ctx.text("status.refreshing", "正在刷新来源…"),
            success_message=lambda _result: self.ctx.text("status.source_refreshed", "来源已刷新"),
            error_code="PLUGIN_STORE_SOURCE_REFRESH_FAILED",
        )

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self._run_async(
            name="plugin_store.source_refresh_all",
            fn=lambda: sources.refresh_all(),
            busy_text=self.ctx.text("status.refreshing", "正在刷新来源…"),
            success_message=lambda _result: self.ctx.text("status.source_refreshed", "来源已刷新"),
            error_code="PLUGIN_STORE_SOURCE_FAILED",
        )

    def _refresh_installed(self) -> None:
        if self._busy:
            return
        self.refresh_all()
        self.set_status(self.ctx.text("status.list_refreshed", "插件列表已刷新"), "success")

    def _remove_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None or self._busy:
            return
        name = next((row["name"] for row in self._source_rows() if row["id"] == source_id), source_id)
        ok = CConfirmDialog.ask(
            self.ctx.parent_window() or self,
            title=self.ctx.text("sources.remove", "移除"),
            message=self.ctx.text(
                "sources.confirm_remove",
                "移除来源「{name}」？已安装插件不受影响。",
            ).format(name=name),
            severity="warn",
        )
        if not ok:
            return

        def done(_result: Any) -> None:
            if self._selection.get("sources") == source_id:
                self._selection["sources"] = ""
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")

        self._run_async(
            name="plugin_store.source_remove",
            fn=lambda: sources.remove(source_id),
            busy_text=self.ctx.text("status.removing_source", "正在移除来源…"),
            success_message=None,
            error_code="PLUGIN_STORE_SOURCE_REMOVE_FAILED",
            on_done=done,
        )

    def _set_source_enabled(self, source_id: str, enabled: bool) -> None:
        if self._busy:
            return
        sources = self._sources()
        if sources is None:
            return
        try:
            sources.set_enabled(source_id, enabled)
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_TOGGLE_FAILED", f"切换源状态失败: {exc}", exc)
            self._sync_item_state(source_id, not enabled)
            return
        self._sync_item_state(source_id, enabled)
        self.refresh_stats()
        self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")

    # ------------------------------------------------------------------
    # 语言 / 主题
    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        """刷新所有常驻文案；列表与检查器随后重建，保留模式/选中/搜索词。"""
        self.eyebrow.setText("SLLKGUI / PLUGINS")
        self.title_label.setText(self.ctx.text("store.title", "插件管理"))
        self.subtitle_label.setText(self.ctx.text("store.subtitle", "已安装、发现与来源，在一处完成"))
        self.stat_installed.set_caption(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled.set_caption(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources.set_caption(self.ctx.text("stats.sources", "来源"))
        self.refresh_button.setText(self.ctx.text("action.refresh", "刷新"))
        self.refresh_sources_button.setText(self.ctx.text("action.refresh_sources", "刷新来源"))
        self.add_source_button.setText(self.ctx.text("action.add_source", "添加来源"))
        self.search.setPlaceholderText(
            {
                "installed": self.ctx.text("installed.filter", "过滤插件…"),
                "discover": self.ctx.text("discover.placeholder", "搜索插件名称、简介或作者…"),
                "sources": self.ctx.text("sources.placeholder", "搜索来源…"),
            }[self.mode]
        )
        self.mode_tabs.set_options(self._mode_labels(), index=self._mode_index(), emit=False)
        self._sync_actions()
        # 文案变了：递增版本让行与详情重建一次，其余状态保持不变。
        self._view_revision += 1
        self.refresh_all()

    def _theme_changed(self) -> None:
        self.setStyleSheet(page_sheet())
        for widget in self.findChildren(QWidget):
            widget.update()

    def _reload_one(self, plugin_id: str, reason: str, *, load: bool = True) -> None:
        """只刷新目标插件；宿主不支持时回退到全量重载。"""
        window = self.ctx.parent_window()
        if window is None:
            return
        reloader = getattr(window, "reload_plugin_in_place", None)
        if callable(reloader):

            def run() -> None:
                try:
                    result = reloader(plugin_id, reason=reason, load=load)
                except Exception as exc:  # noqa: BLE001 - 重载失败由运行时记录，页面保持原样
                    self.ctx.log(f"选择性重载失败: {exc}", "warning")
                    return
                try:
                    # 重载只影响诊断区块与启停态，不重建列表/详情。
                    actual = self._plugin_enabled(plugin_id)
                    if actual is not None:
                        self._sync_item_state(plugin_id, actual)
                    if not getattr(result, "ok", True):
                        # 运行时可能已回滚版本：按数据差异原地同步一次。
                        self.refresh_all()
                    self._sync_inspector_history(plugin_id)
                    self.refresh_stats()
                except RuntimeError:  # 页面可能在回退全量重载时已销毁
                    pass

            single_shot(window, 80, run)
            return
        self.schedule_reload()

    def schedule_reload(self) -> None:
        """全量重载回退路径；停留在本页并恢复界面状态。

        选择性重载可用时由 :meth:`_reload_one` 走 ``reload_plugin_in_place``；
        本方法只保留给未实现选择性重载的宿主。
        """
        window = self.ctx.parent_window()
        if window is None:
            return
        self._stash_state(window)
        reloader = getattr(window, "reload_plugins", None)
        if not callable(reloader):
            return
        page_object = str(self.objectName() or "")
        single_shot(window, 120, lambda: reloader(page_object))

    # ------------------------------------------------------------------
    # 界面状态存取（跨页面重建）
    # ------------------------------------------------------------------
    #: 记录在本页宿主窗口上的属性名
    _STATE_ATTR = "_plugin_store_ui_state"

    def _stash_state(self, window) -> None:
        try:
            setattr(
                window,
                self._STATE_ATTR,
                {
                    "mode": self.mode,
                    "query": self.query,
                    "selection": dict(self._selection),
                    "list_scroll": self.list_panel.scroll.verticalScrollBar().value(),
                },
            )
        except Exception as exc:  # noqa: BLE001 - 状态保存失败不能阻断重载
            self.ctx.log(f"保存插件管理页状态失败: {exc}", "warning")

    def _restore_state(self) -> None:
        """取回上一次重建前保存的界面状态；没有则保持默认。"""
        window = self.ctx.parent_window()
        state = getattr(window, self._STATE_ATTR, None) if window is not None else None
        if not isinstance(state, dict):
            return
        try:
            if window is not None:
                setattr(window, self._STATE_ATTR, None)
            selection = state.get("selection")
            if isinstance(selection, dict):
                for mode in self._selection:
                    value = str(selection.get(mode) or "")
                    if value:
                        self._selection[mode] = value
            query = str(state.get("query") or "")
            if query:
                self.query = query
                self.search.blockSignals(True)
                self.search.setText(query)
                self.search.blockSignals(False)
            mode = str(state.get("mode") or "")
            if mode in {item[0] for item in self._MODE_SPECS}:
                self._restore_mode = mode
            scroll = state.get("list_scroll")
            if isinstance(scroll, int) and scroll > 0:
                self._restore_scroll = scroll
        except Exception as exc:  # noqa: BLE001 - 状态恢复失败退化为默认视图
            self.ctx.log(f"恢复插件管理页状态失败: {exc}", "warning")


__all__ = ["PageContext", "StorePage", "build_plugin_store_page"]
