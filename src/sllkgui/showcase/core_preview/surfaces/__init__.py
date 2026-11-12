"""Surface 页面惰性加载表。"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sllkgui.plugin import GalleryContext


def load_page(surface: str, ctx: GalleryContext):
    module = importlib.import_module(f".{surface}.page", __package__)
    return module.build(ctx)


__all__ = ["load_page"]
