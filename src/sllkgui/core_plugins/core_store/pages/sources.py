"""源管理页：添加、刷新、移除插件源。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from sllkgui.guicore import CButton, CConfirmDialog, CInputText
from sllkgui.plugin import GalleryContext

from .base import make_table, page_shell, selected_row


class SourcesPage(QWidget):
    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        layout, card_layout, header = page_shell(ctx, "sources.title", "插件源", self)

        self.url = CInputText(placeholder=ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_btn = CButton(ctx.text("actions.add", "添加"), size="sm")
        self.refresh_btn = CButton(ctx.text("actions.refresh", "刷新"), size="sm", severity="secondary", variant="outlined")
        self.remove_btn = CButton(ctx.text("actions.remove", "移除"), size="sm", severity="danger", variant="outlined")
        header.addWidget(self.url, 1)
        header.addWidget(self.add_btn)
        header.addWidget(self.refresh_btn)
        header.addWidget(self.remove_btn)

        self.table = make_table(
            ctx,
            [
                ("id", "源"),
                ("url", "地址"),
                ("trust", "信任"),
                ("last_refresh", "最近刷新"),
            ],
        )
        card_layout.addWidget(self.table, 1)
        self.add_btn.clicked.connect(self._add)
        self.refresh_btn.clicked.connect(self._refresh)
        self.remove_btn.clicked.connect(self._remove)
        self.refresh()

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    def refresh(self) -> None:
        sources = self._sources()
        rows = []
        if sources is not None:
            rows = [
                {
                    "id": record.source_id,
                    "url": record.url,
                    "trust": record.trust,
                    "last_refresh": record.last_refresh or "-",
                }
                for record in sources.list()
            ]
        self.table.set_rows(rows)

    def _add(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        url = self.url.text().strip()
        if not url:
            return
        try:
            record = sources.add(url)
            self.ctx.event("core_store.source_added", {"id": record.source_id})
            self.url.setText("")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_ADD_FAILED", f"添加源失败: {exc}", str(exc))
        self.refresh()

    def _refresh(self) -> None:
        sources = self._sources()
        row = selected_row(self.table)
        if sources is None or not row:
            return
        try:
            with self.ctx.timing("core_store.source_refresh"):
                sources.refresh(str(row.get("id")))
            self.ctx.event("core_store.source_refreshed", {"id": row.get("id")})
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_REFRESH_FAILED", f"刷新源失败: {exc}", str(exc))
        self.refresh()

    def _remove(self) -> None:
        sources = self._sources()
        row = selected_row(self.table)
        if sources is None or not row:
            return
        source_id = str(row.get("id"))
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("actions.remove", "移除"),
            message=self.ctx.text("confirm.remove_source", f"移除源 {source_id}？已安装插件不受影响。"),
            severity="warn",
        )
        if not ok:
            return
        try:
            sources.remove(source_id)
            self.ctx.event("core_store.source_removed", {"id": source_id})
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_REMOVE_FAILED", f"移除源失败: {exc}", str(exc))
        self.refresh()


__all__ = ["SourcesPage"]
