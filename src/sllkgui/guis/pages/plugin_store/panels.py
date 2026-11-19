"""三段工作区面板：已安装 / 发现 / 源，统一 DataView + 工具栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.guicore import (
    CButton,
    CDataView,
    CInputText,
    CSelectButton,
)

from .dialogs import _PluginDetailDialog, _SourceDetailDialog
from .entries import _build_entry

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查，避免与 page.py 循环导入
    from .page import StorePage


class _StorePanel(QWidget):
    """DataView 面板基类：统一工具栏、视图切换与数据视图。"""

    def __init__(self, page: StorePage, empty_text: str, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._view_mode = "list"
        self.data_view = CDataView(
            [],
            self._template,
            layout="list",
            columns=2,
            empty_text=empty_text,
            parent=self,
        )
        self._build()
        self.refresh()

    def _build(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _template(self, record: dict[str, Any]) -> QWidget:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def refresh(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _manager(self):
        return self.page._manager()

    def _sources(self):
        return self.page._sources()

    def _add_view_toggle(self, toolbar: QHBoxLayout) -> None:
        options = [self.ctx.text("view.grid", "网格"), self.ctx.text("view.list", "列表")]
        self.view_toggle = CSelectButton(options, index=1, size="sm")
        self.view_toggle.setFixedWidth(120)
        self.view_toggle.selectionChanged.connect(self._on_view_index)
        toolbar.addWidget(self.view_toggle)

    def _on_view_index(self, index: int) -> None:
        self._view_mode = "grid" if index == 0 else "list"
        self.data_view.set_layout(self._view_mode)


class _InstalledPanel(_StorePanel):
    """已安装：过滤 + DataView；条目开关直接启停，详情承载其余操作。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        self._rows: list[dict[str, Any]] = []
        super().__init__(page, page.ctx.text("installed.empty", "还没有安装插件，去「发现」看看"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = CInputText(placeholder=self.ctx.text("installed.filter", "过滤插件…"), icon="icon_search")
        self.filter.setFixedWidth(240)
        toolbar.addWidget(self.filter)
        toolbar.addStretch(1)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self.filter.textChanged.connect(self._apply_filter)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "installed", self.ctx, self._on_toggle)

    def _on_toggle(self, plugin_id: str, enabled: bool) -> None:
        self.page._set_plugin_enabled(plugin_id, enabled)

    def _apply_filter(self) -> None:
        needle = self.filter.text().strip().lower()
        rows = [
            row
            for row in self._rows
            if not needle
            or needle in f"{row.get('id')} {row.get('name')} {row.get('source')}".lower()
        ]
        self.data_view.set_rows(rows)

    def refresh(self) -> None:
        manager = self._manager()
        self._rows = list(manager.installed_rows()) if manager is not None else []
        self._apply_filter()

    def _open_detail(self, record: dict[str, Any]) -> None:
        _PluginDetailDialog(self.page, record, installed=True).open()


class _DiscoverPanel(_StorePanel):
    """发现：搜索结果（含已安装）与安装/启停详情。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(page, page.ctx.text("discover.empty", "没有匹配的可安装插件"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.query = CInputText(
            placeholder=self.ctx.text("discover.placeholder", "搜索插件名称、ID 或简介…"),
            icon="icon_search",
        )
        self.refresh_btn = CButton(
            "",
            icon="icon_refresh",
            variant="text",
            size="sm",
            fixed_width=34,
            icon_size=20,
        )
        self.refresh_btn.setToolTip(self.ctx.text("discover.refresh_sources", "刷新源"))
        toolbar.addWidget(self.query, 1)
        toolbar.addWidget(self.refresh_btn)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self.search)
        self.query.textChanged.connect(lambda: self._search_timer.start())
        self.query.returnPressed.connect(self.search)
        self.refresh_btn.clicked.connect(self._refresh_sources)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "discover", self.ctx, self._on_toggle)

    def refresh(self) -> None:
        self.search()

    def search(self) -> None:
        manager = self._manager()
        if manager is None:
            self.data_view.set_rows([])
            self.page.update_discover_count(0)
            return
        needle = self.query.text().strip().lower()
        installed = {str(row.get("id") or ""): row for row in manager.installed_rows()}
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in manager.search(needle):
            plugin_id = str(row.get("id") or "")
            if plugin_id in seen:
                continue
            seen.add(plugin_id)
            current = installed.get(plugin_id)
            row["installed"] = current is not None
            row["enabled"] = bool(current.get("enabled")) if current is not None else False
            row["installed_version"] = str(current.get("version") or "") if current is not None else ""
            rows.append(row)

        # 已安装但源索引暂时没有的插件仍要出现在发现页，并标记「已安装」。
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
        self.data_view.set_rows(rows)
        self.page.update_discover_count(len(rows))

    def _on_toggle(self, plugin_id: str, enabled: bool) -> None:
        self.page._set_plugin_enabled(plugin_id, enabled)

    def _open_detail(self, record: dict[str, Any]) -> None:
        _PluginDetailDialog(self.page, record, installed=bool(record.get("installed"))).open()

    def _refresh_sources(self) -> None:
        self.page._refresh_sources()


class _SourcesPanel(_StorePanel):
    """源：添加输入 + DataView；开关控制源是否参与索引。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(page, page.ctx.text("sources.empty", "还没有配置插件源"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.url = CInputText(placeholder=self.ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_btn = CButton(self.ctx.text("sources.add", "添加"), size="sm")
        toolbar.addWidget(self.url, 1)
        toolbar.addWidget(self.add_btn)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self.add_btn.clicked.connect(self._add)
        self.url.returnPressed.connect(self._add)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "source", self.ctx, self._on_toggle)

    def refresh(self) -> None:
        sources = self._sources()
        rows = (
            [
                {
                    "id": record.source_id,
                    "url": record.url,
                    "trust": record.trust,
                    "enabled": record.enabled,
                    "commit": record.commit,
                    "last_refresh": record.last_refresh,
                }
                for record in sources.list()
            ]
            if sources is not None
            else []
        )
        self.data_view.set_rows(rows)

    def _add(self) -> None:
        if self.page._add_source(self.url.text().strip()):
            self.url.setText("")

    def _on_toggle(self, source_id: str, enabled: bool) -> None:
        self.page._set_source_enabled(source_id, enabled)

    def _open_detail(self, record: dict[str, Any]) -> None:
        _SourceDetailDialog(self.page, record).open()


# ----------------------------------------------------------------------
# 页面
