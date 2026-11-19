"""详情对话框：插件与源的只读信息 + 操作入口。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.guicore import CButton, CDialog, CHDiv, CIconTile, CText, single_shot

from .entries import _chip, _detail_hero, _meta_grid, _permission_block

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查，避免与 page.py 循环导入
    from .page import StorePage


class _DetailDialogBase:
    """详情对话框基类：统一关闭动画、引用清理与动作执行时机。"""

    def __init__(self, page: StorePage, title: str) -> None:
        self.page = page
        self.ctx = page.ctx
        parent = self.ctx.parent_window() or page.window()
        self.dialog = CDialog(title=title, width="lg", parent=parent)
        self._ran = False
        self._executed = False
        self.dialog.closed.connect(self._release)
        page._detail_dialog = self.dialog

    def _release(self) -> None:
        if self.page._detail_dialog is self.dialog:
            self.page._detail_dialog = None

    def open(self) -> None:
        self.dialog.open_dialog()

    def _run(self, callback: Callable[[], None]) -> None:
        """先收起详情，再执行动作，避免两个浮层同时出现。"""
        if self._ran:
            return
        self._ran = True

        def once() -> None:
            if self._executed:
                return
            self._executed = True
            callback()

        # 等详情对话框的模态状态与窗口激活彻底结束，再执行下一步；
        # 否则紧接着弹出的确认框可能拿不到输入焦点，表现为整个窗口“卡死”。
        self.dialog.closed.connect(lambda: single_shot(self.page, 0, once))
        self.dialog.reject()

    def _action(
        self,
        key: str,
        fallback: str,
        callback: Callable[[], None],
        *,
        severity: str,
        variant: str,
        icon: str,
    ) -> CButton:
        return self.dialog.add_action_button(
            self.ctx.text(key, fallback),
            lambda: self._run(callback),
            severity=severity,
            variant=variant,
            icon=icon,
        )


class _PluginDetailDialog(_DetailDialogBase):
    """插件详情：基础信息、权限与更新/回滚/启停/卸载动作。"""

    def __init__(self, page: StorePage, record: dict[str, Any], *, installed: bool) -> None:
        self.record = dict(record)
        self.installed = bool(installed)
        self.available_version = ""
        if self.installed:
            if record.get("installed"):
                self.available_version = str(record.get("version") or "")
            manager = page._manager()
            if manager is not None:
                current = next(
                    (row for row in manager.installed_rows() if row.get("id") == self.record.get("id")),
                    None,
                )
                if current is not None:
                    for key in ("version", "source", "commit", "path", "permissions", "previous", "enabled", "compliance"):
                        self.record[key] = current.get(key)
        super().__init__(page, page.ctx.text("installed.detail_title", "插件详情"))
        self._build_body()
        self._build_footer()

    def _build_body(self) -> None:
        record = self.record
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(_detail_hero(record, self.ctx, installed=self.installed, icon="icon_store"))
        summary = str(record.get("summary") or self.ctx.text("detail.no_description", "暂无简介"))
        summary_label = CText.with_role("muted", summary)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        layout.addWidget(CHDiv())
        layout.addWidget(CText.with_role("section", self.ctx.text("detail.meta", "基础信息")))

        items: list[tuple[str, str, bool]] = []
        version = str(record.get("version") or "?")
        version_label = self.ctx.text("installed.version", "版本") if self.installed else self.ctx.text("detail.available", "可用版本")
        items.append((version_label, f"v{version}", False))
        if self.available_version and self.available_version != version:
            items.append((self.ctx.text("detail.available", "可用版本"), f"v{self.available_version}", False))
        source = str(record.get("source") or "")
        if source:
            items.append((self.ctx.text("installed.source", "来源"), source, False))
        commit = str(record.get("commit") or "")
        if commit:
            items.append((self.ctx.text("installed.commit", "提交"), commit[:12], True))
        path = str(record.get("path") or "")
        if path:
            items.append((self.ctx.text("installed.path", "目录"), path, True))
        previous = record.get("previous") or {}
        if isinstance(previous, dict) and previous.get("version"):
            items.append((self.ctx.text("detail.previous", "上一版本"), f"v{previous.get('version')}", False))
        compliance = record.get("compliance")
        if compliance not in (None, ""):
            items.append((self.ctx.text("detail.compliance", "合规级别"), str(compliance), False))
        author = str(record.get("author") or "")
        if author:
            items.append((self.ctx.text("detail.author", "作者"), author, False))
        categories = record.get("categories") or []
        if categories:
            items.append(
                (self.ctx.text("detail.categories", "分类"), " / ".join(str(item) for item in categories), False)
            )
        repository = str(record.get("repository") or "")
        if repository:
            items.append((self.ctx.text("detail.repository", "仓库"), repository, True))

        layout.addWidget(_meta_grid(items))
        layout.addWidget(_permission_block(list(record.get("permissions") or []), self.ctx))
        self.dialog.add_widget(body)

    def _build_footer(self) -> None:
        record = self.record
        plugin_id = str(record.get("id") or "")
        if not self.installed:
            self._action(
                "discover.install",
                "安装",
                lambda: self.page._install_plugin(record),
                severity="primary",
                variant="solid",
                icon="icon_add",
            )
            return

        previous = record.get("previous") or {}
        has_previous = isinstance(previous, dict) and bool(previous.get("version"))
        enabled = bool(record.get("enabled", True))
        self._action(
            "installed.remove",
            "卸载",
            lambda: self.page._remove_plugin(plugin_id),
            severity="danger",
            variant="outlined",
            icon="icon_trash",
        )
        self._action(
            "installed.disable" if enabled else "installed.enable",
            "停用" if enabled else "启用",
            lambda: self.page._set_plugin_enabled(plugin_id, not enabled),
            severity="warn",
            variant="outlined",
            icon="icon_close" if enabled else "icon_check",
        )
        rollback = self._action(
            "installed.rollback",
            "回滚",
            lambda: self.page._rollback_plugin(plugin_id),
            severity="secondary",
            variant="outlined",
            icon="icon_restore",
        )
        rollback.setEnabled(has_previous)
        self._action(
            "installed.update",
            "更新",
            lambda: self.page._update_plugin(plugin_id),
            severity="primary",
            variant="solid",
            icon="icon_refresh",
        )


class _SourceDetailDialog(_DetailDialogBase):
    """源详情：地址、信任级别、刷新与移除。"""

    def __init__(self, page: StorePage, record: dict[str, Any]) -> None:
        self.record = dict(record)
        super().__init__(page, page.ctx.text("sources.detail_title", "源详情"))
        self._build_body()
        self._build_footer()

    def _build_body(self) -> None:
        record = self.record
        enabled = bool(record.get("enabled", True))
        trust = str(record.get("trust") or "user")
        trust_text = self.ctx.text("sources.official", "官方") if trust == "official" else self.ctx.text("sources.user", "用户")

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        key = "installed.enabled" if enabled else "installed.disabled"
        hero = QWidget()
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(14)
        hero_row.addWidget(CIconTile("icon_database", 54), 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(4)
        title = CText.with_role("title", str(record.get("id") or ""))
        title.setWordWrap(True)
        column.addWidget(title)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(_chip(trust_text, accent=trust == "official"))
        chips.addWidget(_chip(self.ctx.text(key, "已启用" if enabled else "已停用"), accent=enabled))
        chips.addStretch(1)
        column.addLayout(chips)
        hero_row.addLayout(column, 1)
        layout.addWidget(hero)

        url_label = CText.with_role("muted", str(record.get("url") or ""), mono=True)
        url_label.setWordWrap(True)
        layout.addWidget(url_label)
        layout.addWidget(CHDiv())
        layout.addWidget(CText.with_role("section", self.ctx.text("detail.meta", "基础信息")))
        layout.addWidget(
            _meta_grid(
                [
                    (self.ctx.text("detail.source_id", "源 ID"), str(record.get("id") or ""), True),
                    (self.ctx.text("detail.url", "地址"), str(record.get("url") or ""), True),
                    (self.ctx.text("detail.trust", "信任级别"), trust_text, False),
                    (self.ctx.text("detail.status", "状态"), self.ctx.text(key, "已启用" if enabled else "已停用"), False),
                    (self.ctx.text("installed.commit", "提交"), str(record.get("commit") or "-")[:12], True),
                    (self.ctx.text("detail.last_refresh", "最近刷新"), str(record.get("last_refresh") or "-"), False),
                ]
            )
        )
        self.dialog.add_widget(body)

    def _build_footer(self) -> None:
        source_id = str(self.record.get("id") or "")
        self._action(
            "sources.remove",
            "移除",
            lambda: self.page._remove_source(source_id),
            severity="danger",
            variant="outlined",
            icon="icon_trash",
        )
        self._action(
            "sources.refresh",
            "刷新",
            lambda: self.page._refresh_source(source_id),
            severity="primary",
            variant="solid",
            icon="icon_refresh",
        )


# ----------------------------------------------------------------------
# 三个数据面板
