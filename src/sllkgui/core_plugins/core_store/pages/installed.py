"""已安装插件页：列表、启停、更新、回滚、卸载。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QWidget

from sllkgui.guicore import CButton, CConfirmDialog
from sllkgui.plugin import GalleryContext

from .base import make_table, page_shell, selected_row


class InstalledPage(QWidget):
    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.runtime = self._runtime()
        layout, card_layout, header = page_shell(ctx, "installed.title", "已安装插件", self)

        self.refresh_btn = CButton(ctx.text("actions.refresh", "刷新"), size="sm", severity="secondary", variant="outlined")
        self.update_btn = CButton(ctx.text("actions.update", "更新"), size="sm")
        self.rollback_btn = CButton(ctx.text("actions.rollback", "回滚"), size="sm", severity="secondary", variant="outlined")
        self.toggle_btn = CButton(ctx.text("actions.disable", "禁用"), size="sm", severity="warn", variant="outlined")
        self.remove_btn = CButton(ctx.text("actions.remove", "卸载"), size="sm", severity="danger", variant="outlined")
        for button in (self.refresh_btn, self.update_btn, self.rollback_btn, self.toggle_btn, self.remove_btn):
            header.addWidget(button)

        self.table = make_table(
            ctx,
            [
                ("id", "插件"),
                ("version", "版本"),
                ("source", "来源"),
                ("enabled", "启用"),
                ("compliance", "合规"),
            ],
        )
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setObjectName("CoreStoreDetail")
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(self.detail)

        self.refresh_btn.clicked.connect(self.refresh)
        self.update_btn.clicked.connect(self._update)
        self.rollback_btn.clicked.connect(self._rollback)
        self.toggle_btn.clicked.connect(self._toggle)
        self.remove_btn.clicked.connect(self._remove)
        self.table.selectionChanged.connect(self._show_detail)
        self.refresh()

    def _runtime(self):
        from sllkgui.gallery.runtime import current_runtime

        return current_runtime()

    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def refresh(self) -> None:
        manager = self._manager()
        rows = manager.installed_rows() if manager is not None else []
        self.table.set_rows(
            [
                {
                    **row,
                    "enabled": self.ctx.text("status.enabled", "是") if row["enabled"] else self.ctx.text("status.disabled", "否"),
                    "compliance": f"v{row['compliance']}",
                }
                for row in rows
            ]
        )
        self.ctx.log(f"refreshed installed plugins: {len(rows)}")

    def _show_detail(self, _rows=None) -> None:
        row = selected_row(self.table)
        if not row:
            self.detail.setText("")
            return
        self.detail.setText(
            f"{row.get('id')} · {row.get('version')} · commit {str(row.get('commit') or '')[:8]}\n"
            f"{self.ctx.text('columns.path', '目录')}: {row.get('path')}\n"
            f"{self.ctx.text('columns.permissions', '权限')}: {', '.join(row.get('permissions') or []) or '-'}"
        )

    def _run_action(self, name: str, action) -> None:
        try:
            with self.ctx.timing(f"core_store.{name}"):
                result = action()
            self.ctx.log(f"{name}: {result}")
            self.ctx.event(f"core_store.{name}", {"result": str(result)})
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self.ctx.report_error("CORE_STORE_ACTION_FAILED", f"{name} 失败: {exc}", str(exc))
        self.refresh()
        self._schedule_reload()

    def _schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            QTimer.singleShot(80, window.reload_plugins)

    def _current_id(self) -> str:
        row = selected_row(self.table)
        return str(row.get("id") or "") if row else ""

    def _update(self) -> None:
        plugin_id = self._current_id()
        if plugin_id:
            self._run_action("update", lambda: self._manager().update(plugin_id))

    def _rollback(self) -> None:
        plugin_id = self._current_id()
        if plugin_id:
            self._run_action("rollback", lambda: self._manager().rollback(plugin_id))

    def _toggle(self) -> None:
        row = selected_row(self.table)
        if not row:
            return
        plugin_id = str(row.get("id") or "")
        enabled = bool(row.get("enabled") == self.ctx.text("status.enabled", "是"))
        self._run_action("toggle", lambda: self._manager().set_enabled(plugin_id, not enabled))

    def _remove(self) -> None:
        plugin_id = self._current_id()
        if not plugin_id:
            return
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("actions.remove", "卸载"),
            message=self.ctx.text("confirm.remove", f"确定卸载 {plugin_id}？数据目录默认保留。"),
            severity="danger",
        )
        if not ok:
            return
        self._run_action("remove", lambda: self._manager().remove(plugin_id))


__all__ = ["InstalledPage"]
