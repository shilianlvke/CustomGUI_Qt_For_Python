"""核心插件：插件管理（已安装 / 搜索安装 / 源管理）。

``sllkgui run`` 始终加载本插件（``--safe-mode`` 也加载），保证用户在任何
状态下都能进入插件管理。
"""

from __future__ import annotations

from sllkgui.plugin import GalleryContext, Plugin

_PAGES = {
    "installed": ("installed", "InstalledPage"),
    "search": ("search", "SearchPage"),
    "sources": ("sources", "SourcesPage"),
}


def _factory(surface: str):
    module_name, class_name = _PAGES[surface]

    def build(ctx: GalleryContext):
        from .pages import load_page

        with ctx.timing(f"core_store.{surface}.build"):
            page = load_page(module_name, class_name, ctx)
        ctx.event("surface.ready", {"surface": surface})
        return page

    return build


class CoreStorePlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading core store plugin")
        with ctx.timing("core_store.load"):
            from sllkgui.gallery.runtime import current_runtime

            self.runtime = current_runtime()
        ctx.event("core_store.loaded")

    def surfaces(self):
        return {surface: _factory(surface) for surface in _PAGES}

    def on_unload(self) -> None:
        self.ctx.log("unloading core store plugin")
        self.ctx.event("core_store.unloaded")


PLUGIN = CoreStorePlugin()
