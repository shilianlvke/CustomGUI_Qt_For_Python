"""表格列定义 ``CTableColumn``（对应 PrimeVue 的 ``Column``）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class CTableColumn:
    """表格列定义（对应 PrimeVue 的 ``Column``）。"""

    field: str
    header: str = ""
    width: int | None = None
    align: str = "left"
    min_width: int = 90
    sortable: bool = True
    filterable: bool = True
    frozen: bool = False
    formatter: Callable[[Any, dict], str] | None = None
    tag: Callable[[Any, dict], tuple[str, str] | None] | None = None
    expander: bool = False

    def text(self, value: Any, record: dict) -> str:
        if self.formatter is not None:
            return str(self.formatter(value, record))
        return "" if value is None else str(value)

    def tag_for(self, value: Any, record: dict) -> tuple[str, str] | None:
        if self.tag is None:
            return None
        result = self.tag(value, record)
        if result is None:
            return None
        severity, text = result
        return str(severity), str(text)


__all__ = ["CTableColumn"]
