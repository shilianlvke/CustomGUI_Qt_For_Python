"""工作区内嵌详情检查器。

替代模态详情对话框：常驻在工作区右侧，选中条目即更新内容，动作按钮直接
调用页面既有的业务方法，保持与旧对话框一致的行为契约（先关浮层再执行的
时序不再需要）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from sllkgui.guicore import CButton, CSurfacePanel, CText

from .entries import _chip, _detail_hero, _meta_grid, _permission_block

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from .page import StorePage


class InlineInspector(CSurfacePanel):
    """选中条目后的详情与动作面板。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(radius=8, parent=parent)
        self.page = page
        self.ctx = page.ctx
        self.record: dict[str, Any] | None = None
        self.kind = ""
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        label = CText.with_role("muted", self.ctx.text("installed.select_hint", "选择一个插件查看详情"))
        label.setWordWrap(True)
        empty_layout.addStretch(1)
        empty_layout.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)
        self._stack.addWidget(empty)  # index 0: 空态
        self._stack.setCurrentIndex(0)

    def _clear(self) -> None:
        self._stack.setCurrentIndex(0)

    def _replace(self, widget: QWidget) -> None:
        while self._stack.count() > 1:
            old = self._stack.widget(1)
            self._stack.removeWidget(old)
            old.deleteLater()
        self._stack.addWidget(widget)
        self._stack.setCurrentIndex(1)

    def show_record(self, record: dict[str, Any], *, kind: str, installed: bool) -> None:
        """渲染一条记录；``kind`` 为 installed / discover / sources。"""
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        if kind == "sources":
            title = str(record.get("id") or record.get("url") or "")
            hero = QWidget()
            hero_layout = QHBoxLayout(hero)
            hero_layout.setContentsMargins(0, 0, 0, 0)
            hero_layout.addWidget(
                _chip(
                    self.ctx.text("sources.official", "官方")
                    if record.get("trust") == "official"
                    else self.ctx.text("sources.user", "用户"),
                    accent=True,
                )
            )
            hero_layout.addWidget(
                _chip(
                    self.ctx.text("installed.enabled", "已启用")
                    if record.get("enabled", True)
                    else self.ctx.text("installed.disabled", "已停用"),
                    accent=bool(record.get("enabled", True)),
                )
            )
            hero_layout.addStretch(1)
            layout.addWidget(CText.with_role("title", title))
            layout.addWidget(hero)
            summary = CText.with_role("muted", str(record.get("url") or ""), mono=True)
            summary.setWordWrap(True)
            layout.addWidget(summary)
            layout.addWidget(CText.with_role("section", self.ctx.text("detail.meta", "基础信息")))
            layout.addWidget(
                _meta_grid(
                    [
                        (self.ctx.text("detail.source_id", "源 ID"), str(record.get("id") or ""), True),
                        (self.ctx.text("detail.url", "地址"), str(record.get("url") or ""), True),
                        (self.ctx.text("detail.trust", "信任级别"), str(record.get("trust") or ""), False),
                        (self.ctx.text("installed.commit", "提交"), str(record.get("commit") or "")[:12], True),
                        (
                            self.ctx.text("detail.last_refresh", "最近刷新"),
                            str(record.get("last_refresh") or ""),
                            False,
                        ),
                    ]
                )
            )
            layout.addStretch(1)
            footer = QHBoxLayout()
            refresh = CButton(self.ctx.text("sources.refresh", "刷新"), severity="primary", variant="solid")
            remove = CButton(self.ctx.text("sources.remove", "移除"), severity="danger", variant="outlined")
            refresh.clicked.connect(lambda: self.page._refresh_source(str(record.get("id") or "")))
            remove.clicked.connect(lambda: self.page._remove_source(str(record.get("id") or "")))
            footer.addWidget(refresh)
            footer.addWidget(remove)
            layout.addLayout(footer)
        else:
            merged = dict(record)
            if installed:
                manager = self.page._manager()
                current = (
                    next(
                        (row for row in manager.installed_rows() if row.get("id") == merged.get("id")),
                        None,
                    )
                    if manager is not None
                    else None
                )
                if current is not None:
                    for key in (
                        "version",
                        "source",
                        "commit",
                        "path",
                        "permissions",
                        "previous",
                        "enabled",
                        "compliance",
                        "author",
                        "categories",
                    ):
                        merged[key] = current.get(key, merged.get(key))
            layout.addWidget(_detail_hero(merged, self.ctx, installed=installed, icon="icon_store"))
            summary = CText.with_role(
                "muted", str(merged.get("summary") or self.ctx.text("detail.no_description", "暂无简介"))
            )
            summary.setWordWrap(True)
            layout.addWidget(summary)
            layout.addWidget(CText.with_role("section", self.ctx.text("detail.meta", "基础信息")))
            items: list[tuple[str, str, bool]] = [
                (self.ctx.text("installed.version", "版本"), f"v{merged.get('version') or '?'}", False),
                (self.ctx.text("installed.source", "来源"), str(merged.get("source") or ""), False),
                (self.ctx.text("detail.author", "作者"), str(merged.get("author") or ""), False),
                (
                    self.ctx.text("detail.categories", "分类"),
                    " / ".join(str(x) for x in merged.get("categories") or []),
                    False,
                ),
                (self.ctx.text("installed.commit", "提交"), str(merged.get("commit") or "")[:12], True),
                (self.ctx.text("detail.compliance", "合规级别"), str(merged.get("compliance") or ""), False),
            ]
            layout.addWidget(_meta_grid([item for item in items if item[1]]))
            layout.addWidget(_permission_block(list(merged.get("permissions") or []), self.ctx))
            available = str(merged.get("available_version") or "")
            if available and available != str(merged.get("version") or ""):
                layout.addWidget(_chip(f"{self.ctx.text('detail.available', '可用版本')} v{available}", accent=True))
            layout.addStretch(1)
            footer = QHBoxLayout()
            plugin_id = str(merged.get("id") or "")
            if not installed:
                install = CButton(self.ctx.text("discover.install", "安装"), severity="primary", variant="solid")
                install.clicked.connect(lambda: self.page._install_plugin(merged))
                footer.addWidget(install)
            else:
                previous = merged.get("previous") or {}
                rollback = CButton(
                    self.ctx.text("installed.rollback", "回滚"), severity="secondary", variant="outlined"
                )
                rollback.setEnabled(isinstance(previous, dict) and bool(previous.get("version")))
                update = CButton(self.ctx.text("installed.update", "更新"), severity="primary", variant="solid")
                toggle = CButton(
                    self.ctx.text("installed.disable", "停用")
                    if merged.get("enabled", True)
                    else self.ctx.text("installed.enable", "启用"),
                    severity="warn",
                    variant="outlined",
                )
                remove = CButton(self.ctx.text("installed.remove", "卸载"), severity="danger", variant="outlined")
                rollback.clicked.connect(lambda: self.page._rollback_plugin(plugin_id))
                update.clicked.connect(lambda: self.page._update_plugin(plugin_id))
                toggle.clicked.connect(
                    lambda: self.page._set_plugin_enabled(plugin_id, not bool(merged.get("enabled", True)))
                )
                remove.clicked.connect(lambda: self.page._remove_plugin(plugin_id))
                for button in (remove, toggle, rollback, update):
                    footer.addWidget(button)
            layout.addLayout(footer)

        self._replace(body)
        self.record = record
        self.kind = kind

    def clear(self) -> None:
        self.record = None
        self.kind = ""
        self._clear()


__all__ = ["InlineInspector"]
