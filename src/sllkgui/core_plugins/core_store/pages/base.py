"""插件管理页面公共部件。"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sllkgui.guicore import CCard, CDataTable, CTableColumn
from sllkgui.plugin import GalleryContext


def page_shell(
    ctx: GalleryContext,
    title_key: str,
    title_default: str,
    page: QWidget | None = None,
) -> tuple[QWidget, QVBoxLayout, QHBoxLayout]:
    page = page if page is not None else QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(12, 12, 12, 12)
    outer.setSpacing(8)
    header = QHBoxLayout()
    header.setSpacing(8)
    title = QLabel(ctx.text(title_key, title_default))
    title.setObjectName("CoreStoreTitle")
    header.addWidget(title)
    header.addStretch(1)
    outer.addLayout(header)
    card = CCard()
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(10, 8, 10, 10)
    card_layout.setSpacing(8)
    outer.addWidget(card, 1)
    return page, card_layout, header


def make_table(ctx: GalleryContext, columns: list[tuple[str, str]]) -> CDataTable:
    return CDataTable(
        columns=[CTableColumn(field=field, header=ctx.text(f"columns.{field}", header)) for field, header in columns],
        rows=[],
        page_size=10,
        paginator=True,
        selection_mode="single",
        empty_text=ctx.text("empty", "No records"),
    )


def selected_row(table: CDataTable) -> dict[str, Any] | None:
    try:
        record = table.current_record()
    except Exception:
        record = None
    return record or None


__all__ = ["make_table", "page_shell", "selected_row"]
