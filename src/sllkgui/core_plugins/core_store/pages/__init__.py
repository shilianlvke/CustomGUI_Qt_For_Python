"""插件管理页面惰性加载。"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sllkgui.plugin import GalleryContext


def load_page(module_name: str, class_name: str, ctx: GalleryContext):
    module = importlib.import_module(f".{module_name}", __package__)
    return getattr(module, class_name)(ctx)


__all__ = ["load_page"]
