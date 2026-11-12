"""基座原生页面：不经过插件协议、两种模式都常驻的内置页面。

页面描述只包含路由、菜单文案与惰性工厂；控件本身在首次导航时才构建，
与插件 Surface 的加载时机保持一致。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget

from sllkgui.appcore import Language


@dataclass(frozen=True)
class NativePage:
    page_object: str
    button_id: str
    title_key: str
    title_fallback: str
    icon: str
    order: int
    factory: Callable[[Any], QWidget]


def _build_plugin_store(window) -> QWidget:
    from sllkgui.guis.pages.plugin_store import build_plugin_store_page

    return build_plugin_store_page(window)


NATIVE_PAGES: tuple[NativePage, ...] = (
    NativePage(
        page_object="page_native_plugin_store",
        button_id="btn_native_plugin_store",
        title_key="language.plugin_store.store.title",
        title_fallback="插件管理",
        icon="icon_store",
        order=10,
        factory=_build_plugin_store,
    ),
)


def native_page_for(page_object: str) -> NativePage | None:
    return next((page for page in NATIVE_PAGES if page.page_object == page_object), None)


def native_menu_items() -> list[dict[str, Any]]:
    """左菜单底部轨道的原生入口（与插件页面按钮同样由语言键驱动）。"""
    items: list[dict[str, Any]] = []
    for page in sorted(NATIVE_PAGES, key=lambda item: item.order):
        title = str(Language.resolve_key(page.title_key, page.title_fallback))
        items.append(
            {
                "btn_icon": page.icon,
                "btn_id": page.button_id,
                "btn_text": page.title_key,
                "btn_tooltip": page.title_key,
                "btn_text_fallback": title,
                "show_top": False,
                "is_active": False,
            }
        )
    return items


def native_page_routes() -> dict[str, tuple[str, str]]:
    return {
        page.button_id: (page.page_object, str(Language.resolve_key(page.title_key, page.title_fallback)))
        for page in NATIVE_PAGES
    }


__all__ = [
    "NATIVE_PAGES",
    "NativePage",
    "native_menu_items",
    "native_page_for",
    "native_page_routes",
]
