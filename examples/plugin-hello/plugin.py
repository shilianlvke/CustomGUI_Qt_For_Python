"""插件入口：唯一合法导出是 ``PLUGIN`` 实例。"""

from __future__ import annotations

from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx: GalleryContext):
    from .pages.home import HomePage

    with ctx.timing("home.surface.build"):
        page = HomePage(ctx)
    ctx.event("surface.ready", {{"surface": "home"}})
    return page


class SamplePlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading sample plugin")
        with ctx.timing("sample.load"):
            self.data_file = ctx.data_dir / "state.json"
        ctx.event("sample.loaded")

    def surfaces(self):
        return {{"home": build_home}}

    def on_unload(self) -> None:
        self.ctx.log("unloading sample plugin")
        self.ctx.event("sample.unloaded")


PLUGIN = SamplePlugin()
