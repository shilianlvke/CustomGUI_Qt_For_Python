"""插件搜索与安装页。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from sllkgui.guicore import CButton, CConfirmDialog, CInputText
from sllkgui.plugin import GalleryContext

from .base import make_table, page_shell, selected_row


class SearchPage(QWidget):
    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        layout, card_layout, header = page_shell(ctx, "search.title", "搜索插件", self)

        self.query = CInputText(placeholder=ctx.text("search.placeholder", "搜索名称或 ID"))
        self.search_btn = CButton(ctx.text("actions.search", "搜索"), size="sm")
        self.refresh_btn = CButton(ctx.text("actions.refresh_sources", "刷新源"), size="sm", severity="secondary", variant="outlined")
        self.install_btn = CButton(ctx.text("actions.install", "安装"), size="sm", severity="success")
        header.addWidget(self.query, 1)
        header.addWidget(self.search_btn)
        header.addWidget(self.refresh_btn)
        header.addWidget(self.install_btn)

        self.table = make_table(
            ctx,
            [
                ("id", "插件"),
                ("name", "名称"),
                ("version", "版本"),
                ("source", "来源"),
                ("compliance", "合规"),
            ],
        )
        card_layout.addWidget(self.table, 1)

        self.search_btn.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.refresh_btn.clicked.connect(self._refresh_sources)
        self.install_btn.clicked.connect(self._install)
        self.search()

    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    def search(self) -> None:
        manager = self._manager()
        rows = manager.search(self.query.text().strip()) if manager is not None else []
        self.table.set_rows([{**row, "compliance": f"v{row['compliance']}"} for row in rows])
        self.ctx.log(f"search plugins: {len(rows)}")
        self.ctx.event("core_store.search", {"count": len(rows)})

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        try:
            with self.ctx.timing("core_store.source_refresh"):
                sources.refresh_all()
            self.ctx.event("core_store.sources_refreshed")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
        self.search()

    def _install(self) -> None:
        row = selected_row(self.table)
        if not row:
            return
        plugin_id = str(row.get("id") or "")
        permissions = ", ".join(row.get("permissions") or []) or "-"
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("actions.install", "安装"),
            message=self.ctx.text(
                "confirm.install",
                f"安装 {plugin_id} {row.get('version')}？\n来源：{row.get('source')}\n权限：{permissions}",
            ),
            severity="info",
        )
        if not ok:
            return
        manager = self._manager()
        if manager is None:
            return
        try:
            with self.ctx.timing("core_store.install"):
                result = manager.install(plugin_id, source_id=str(row.get("source") or ""))
            self.ctx.log(f"installed: {result}")
            self.ctx.event("core_store.install", {"id": plugin_id, "version": result.get("version")})
            window = self.ctx.parent_window()
            if window is not None and hasattr(window, "reload_plugins"):
                QTimer.singleShot(80, window.reload_plugins)
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_INSTALL_FAILED", f"安装失败: {exc}", str(exc))
        self.search()


__all__ = ["SearchPage"]
