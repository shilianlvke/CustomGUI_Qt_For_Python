"""Gallery 注册表：插件记录、Surface 路由、菜单分组与默认页。

路由键统一为 ``plugin_id/surface_id``；Qt objectName 与菜单按钮 ID 由路由
派生（只保留字母数字），避免 ``.``、``/`` 出现在 findChild 名称里造成歧义。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sllkgui.appcore import Language

from .api import GalleryContext, Plugin
from .manifest import PluginManifest

_ROUTE_SANITIZE_RE = re.compile(r"[^0-9A-Za-z]+")


def sanitize_route(route: str) -> str:
    return _ROUTE_SANITIZE_RE.sub("_", route).strip("_")


@dataclass
class SurfaceRecord:
    plugin_id: str
    surface_id: str
    title: dict[str, str]
    icon: str
    order: int
    default: bool
    factory: Callable[[GalleryContext], Any]
    plugin: PluginRecord

    @property
    def route(self) -> str:
        return f"{self.plugin_id}/{self.surface_id}"

    @property
    def button_id(self) -> str:
        return f"btn_{sanitize_route(self.route)}"

    @property
    def page_object(self) -> str:
        return f"page_{sanitize_route(self.route)}"

    def display_title(self, language: str | None = None) -> str:
        current = language if isinstance(language, str) and language else Language.current()
        return self.title.get(current) or self.title.get("en_us") or self.surface_id


@dataclass
class PluginRecord:
    manifest: PluginManifest
    plugin: Plugin
    path: Any
    context: GalleryContext | None = None
    enabled: bool = True
    error: str = ""
    compliance: int = 1
    telemetry_seen: bool = False
    is_core: bool = False
    surfaces: dict[str, SurfaceRecord] = field(default_factory=dict)

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    @property
    def name(self) -> str:
        return self.manifest.name


class GalleryRegistry:
    """内存注册表；线程约束：只在 Qt 主线程读写。"""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginRecord] = {}
        self._surfaces: dict[str, SurfaceRecord] = {}
        self._errors: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------
    def add(self, record: PluginRecord) -> None:
        if record.plugin_id in self._plugins:
            self.remove(record.plugin_id)
        self._plugins[record.plugin_id] = record
        factories = record.plugin.surfaces()
        for spec in record.manifest.surfaces:
            factory = factories.get(spec.surface_id)
            if factory is None:
                self._errors.append(
                    {
                        "plugin_id": record.plugin_id,
                        "surface": spec.surface_id,
                        "code": "PLUGIN_SURFACE_FACTORY_MISSING",
                    }
                )
                continue
            surface = SurfaceRecord(
                plugin_id=record.plugin_id,
                surface_id=spec.surface_id,
                title=dict(spec.title),
                icon=spec.icon,
                order=spec.order,
                default=spec.default,
                factory=factory,
                plugin=record,
            )
            record.surfaces[spec.surface_id] = surface
            self._surfaces[surface.route] = surface
        extra = set(factories) - {spec.surface_id for spec in record.manifest.surfaces}
        if extra:
            self._errors.append(
                {
                    "plugin_id": record.plugin_id,
                    "code": "PLUGIN_SURFACE_EXTRA_FACTORY",
                    "detail": ", ".join(sorted(extra)),
                }
            )

    def remove(self, plugin_id: str) -> None:
        record = self._plugins.pop(plugin_id, None)
        if record is None:
            return
        for surface_id in list(record.surfaces):
            self._surfaces.pop(f"{plugin_id}/{surface_id}", None)
        record.surfaces.clear()

    def clear(self) -> None:
        self._plugins.clear()
        self._surfaces.clear()
        self._errors.clear()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @property
    def errors(self) -> list[dict[str, str]]:
        return list(self._errors)

    def plugins(self) -> list[PluginRecord]:
        return list(self._plugins.values())

    def routes(self) -> dict[str, SurfaceRecord]:
        return dict(self._surfaces)

    def surface_count(self) -> int:
        return len(self._surfaces)

    def route_for_button(self, button_id: str) -> SurfaceRecord | None:
        for surface in self._surfaces.values():
            if surface.button_id == button_id:
                return surface
        return None

    def route_for_page(self, page_object: str) -> SurfaceRecord | None:
        for surface in self._surfaces.values():
            if surface.page_object == page_object:
                return surface
        return None

    def get(self, route: str) -> SurfaceRecord | None:
        return self._surfaces.get(route)

    def default_route(self) -> str:
        """优先非核心插件的 default，其次任意 default，最后 order 最小的路由。"""
        surfaces = sorted(self._surfaces.values(), key=lambda item: (item.order, item.route))
        if not surfaces:
            return ""
        non_core = [item for item in surfaces if not item.plugin.is_core]
        for pool in (non_core, surfaces):
            for surface in pool:
                if surface.default:
                    return surface.route
        return (non_core or surfaces)[0].route

    def menu_items(self, language: str | None = None) -> list[dict[str, Any]]:
        """生成左菜单按钮描述；无 Surface 的插件不出现。"""
        items: list[dict[str, Any]] = []
        for surface in sorted(self._surfaces.values(), key=lambda item: (item.plugin.is_core, item.order, item.route)):
            title = surface.display_title(language)
            icon = surface.icon or "icon_star_fill"
            if surface.icon:
                candidate = surface.plugin.manifest.root / surface.icon
                if candidate.is_file():
                    icon = str(candidate)
            items.append(
                {
                    "btn_icon": icon,
                    "btn_id": surface.button_id,
                    "btn_text": f"language.app.{surface.plugin_id}.surface.{surface.surface_id}.title",
                    "btn_tooltip": f"language.app.{surface.plugin_id}.surface.{surface.surface_id}.title",
                    "btn_text_fallback": title,
                    # 核心插件是工具入口（插件管理），与「软件信息」一起放到底部
                    "show_top": not surface.plugin.is_core,
                    "is_active": False,
                }
            )
        return items

    def page_routes(self, language: str | None = None) -> dict[str, tuple[str, str]]:
        """返回 ``{button_id: (page_object, title)}``，供旧窗口装配函数使用。"""
        return {
            surface.button_id: (surface.page_object, surface.display_title(language))
            for surface in self._surfaces.values()
        }

    def menu_surface_of_plugin(self, plugin_id: str) -> list[SurfaceRecord]:
        return [item for item in self._surfaces.values() if item.plugin_id == plugin_id]


_CURRENT: GalleryRegistry | None = None


def set_current_registry(registry: GalleryRegistry | None) -> None:
    global _CURRENT
    _CURRENT = registry


def current_registry() -> GalleryRegistry | None:
    return _CURRENT


__all__ = [
    "GalleryRegistry",
    "PluginRecord",
    "SurfaceRecord",
    "current_registry",
    "sanitize_route",
    "set_current_registry",
]
