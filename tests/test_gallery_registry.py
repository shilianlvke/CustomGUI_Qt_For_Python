from __future__ import annotations

from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.manifest import load_manifest
from sllkgui.gallery.registry import GalleryRegistry, PluginRecord
from sllkgui.plugin import GalleryContext, Plugin


class _Plugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx

    def surfaces(self):
        return {"home": lambda _ctx: object()}


def test_registry_routes_and_default(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    manifest = load_manifest(root)
    plugin = _Plugin()
    registry = GalleryRegistry()
    record = PluginRecord(manifest=manifest, plugin=plugin, path=root, is_core=False)
    registry.add(record)
    assert registry.surface_count() == 1
    assert registry.default_route() == "com.example.hello/home"
    surface = registry.get("com.example.hello/home")
    assert surface.button_id == "btn_com_example_hello_home"
    assert surface.page_object == "page_com_example_hello_home"
    assert registry.route_for_button(surface.button_id) is surface
    assert registry.route_for_page(surface.page_object) is surface
    assert registry.menu_items()[0]["btn_id"] == surface.button_id
    assert registry.menu_items()[0]["show_top"] is True
    registry.remove("com.example.hello")
    assert registry.surface_count() == 0


def test_core_plugin_not_preferred_as_default(tmp_path: Path):
    hello = write_plugin(tmp_path / "hello")
    core = write_plugin(tmp_path / "core", plugin_id="com.example.core")
    registry = GalleryRegistry()
    registry.add(PluginRecord(manifest=load_manifest(hello), plugin=_Plugin(), path=hello))
    registry.add(
        PluginRecord(manifest=load_manifest(core), plugin=_Plugin(), path=core, is_core=True)
    )
    # 非核心插件优先
    assert registry.default_route().startswith("com.example.")
    registry.remove("com.example.hello")
    assert registry.default_route() == "com.example.core/home"


def test_page_routes_accept_language_handler(tmp_path: Path):
    """旧调用方传 Language 单例时不能把单例当 dict 键（unhashable）。"""
    from sllkgui.appcore import Language
    from sllkgui.gallery.registry import set_current_registry
    from sllkgui.guis.windows.main_window.registry import get_page_routes

    root = write_plugin(tmp_path / "hello")
    registry = GalleryRegistry()
    registry.add(PluginRecord(manifest=load_manifest(root), plugin=_Plugin(), path=root))
    set_current_registry(registry)
    try:
        routes = get_page_routes(Language)
        assert routes
        surface = registry.get("com.example.hello/home")
        assert surface.display_title(Language) == "首页"
    finally:
        set_current_registry(None)
