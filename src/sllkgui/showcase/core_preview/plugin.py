"""内置组件预览插件：10 个 Surface，仅 ``sllkgui gallery`` 加载。"""

from __future__ import annotations

from sllkgui.plugin import GalleryContext, Plugin

SURFACES = (
    "buttons",
    "tables",
    "data",
    "feedback",
    "inputs",
    "media",
    "menus",
    "overlays",
    "panels",
    "shell",
)


def _factory(surface: str):
    def build(ctx: GalleryContext):
        from .common import bind_context
        from .surfaces import load_page

        bind_context(ctx)
        with ctx.timing(f"showcase.{surface}.build"):
            page = load_page(surface, ctx)
        return page

    return build


class CorePreviewPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading core preview plugin")
        with ctx.timing("showcase.load"):
            self.surface_count = len(SURFACES)
        ctx.event("showcase.loaded", {"surfaces": self.surface_count})

    def surfaces(self):
        return {surface: _factory(surface) for surface in SURFACES}

    def on_unload(self) -> None:
        self.ctx.log("unloading core preview plugin")
        self.ctx.event("showcase.unloaded")


PLUGIN = CorePreviewPlugin()
