"""核心插件：插件管理工作台（已安装 / 发现 / 源）。

``sllkgui run`` 始终加载本插件（``--safe-mode`` 也加载），保证用户在任何
状态下都能进入插件管理。
"""

from __future__ import annotations

from sllkgui.plugin import GalleryContext, Plugin


def _factory(ctx: GalleryContext):
    from .pages import load_page

    with ctx.timing("core_store.build"):
        page = load_page("store", "StorePage", ctx)
    ctx.event("surface.ready", {"surface": "store"})
    return page


class CoreStorePlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading core store plugin")
        with ctx.timing("core_store.load"):
            from sllkgui.gallery.runtime import current_runtime

            self.runtime = current_runtime()
        ctx.event("core_store.loaded")

    def surfaces(self):
        return {"store": _factory}

    def on_unload(self) -> None:
        self.ctx.log("unloading core store plugin")
        self.ctx.event("core_store.unloaded")


PLUGIN = CoreStorePlugin()
