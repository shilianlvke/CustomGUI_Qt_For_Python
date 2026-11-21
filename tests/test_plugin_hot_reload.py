"""插件选择性热重载：只刷新目标插件及其反向依赖者。"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from gallery_helpers import MANIFEST, write_plugin

from sllkgui.gallery.runtime import GalleryRuntime

_SOURCE = '''"""Hot reload test plugin."""
from sllkgui.plugin import GalleryContext, Plugin


class Page(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel):
    def save_state(self):
        return self.text()

    def restore_state(self, state):
        self.setText(str(state))


def build_home(ctx: GalleryContext):
    return Page("%s")


class P(Plugin):
    def __init__(self):
        self.loads = 0
        self.unloads = 0
        self.marker = "%s"

    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        self.loads += 1

    def surfaces(self):
        return {"home": build_home}

    def on_unload(self) -> None:
        self.unloads += 1


PLUGIN = P()
'''


_CLEANUP_SOURCE = '''"""Hot reload cleanup plugin."""
from sllkgui.plugin import (
    GalleryContext,
    Plugin,
    Setting,
    SettingsPage,
    SettingsSection,
)


class P(Plugin):
    def __init__(self):
        self.event_hits = 0
        self.service = None
        self.unsub = None

    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        self.unsub = ctx.events.subscribe(
            "cleanup.topic",
            lambda topic, payload: setattr(self, "event_hits", self.event_hits + 1),
        )
        self.service = object()
        ctx.services.register(self.service)
        ctx.settings.define(
            SettingsPage(
                page_id="",
                title="Clean",
                sections=(
                    SettingsSection(
                        "A",
                        (Setting.switch("enabled", True, "Enabled"),),
                    ),
                ),
            )
        )

    def surfaces(self):
        from PySide6.QtWidgets import QLabel

        return {"home": lambda ctx: QLabel("clean")}


PLUGIN = P()
'''


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


def _source(label: str, marker: str = "v1") -> str:
    return _SOURCE % (label, marker)


def _runtime(tmp_path: Path, dev: Path) -> GalleryRuntime:
    return GalleryRuntime(
        "run",
        data_dir=tmp_path / "data",
        gallery_dir=tmp_path / "data" / "gallery",
        plugin_dirs=[dev],
        install_missing_deps=False,
        interactive=False,
        check_tools=False,
    )


def _manifest(plugin_id: str, name: str, *, dependency: str = "", version: str = "1.0.0") -> str:
    text = MANIFEST.format(plugin_id=plugin_id, name=name, version=version)
    if dependency:
        text += f"dependencies:\n  - id: {dependency}\n"
    return text


def _write_pair(tmp_path: Path, *, dependent: bool = False) -> tuple[Path, GalleryRuntime]:
    dev = tmp_path / "dev"
    write_plugin(dev / "a", plugin_id="com.example.a", name="A", plugin_source=_source("A"))
    write_plugin(
        dev / "b",
        plugin_id="com.example.b",
        name="B",
        plugin_source=_source("B"),
        manifest_text=_manifest(
            "com.example.b",
            "B",
            dependency="com.example.a" if dependent else "",
        ),
    )
    runtime = _runtime(tmp_path, dev)
    runtime.bootstrap()
    return dev, runtime


def test_selective_reload_only_touches_target(tmp_path: Path, qapp):
    dev, runtime = _write_pair(tmp_path)
    try:
        a_before = runtime.registry.get_plugin("com.example.a")
        b_before = runtime.registry.get_plugin("com.example.b")
        assert a_before is not None and b_before is not None
        assert b_before.plugin.loads == 1

        # 更新 A 的源码与版本，再选择性重载 A
        write_plugin(
            dev / "a",
            plugin_id="com.example.a",
            name="A",
            version="1.1.0",
            plugin_source=_source("A", marker="v2"),
        )
        result = runtime.reload_plugin("com.example.a", reason="update")

        assert result.ok, result.message
        assert result.affected == ["com.example.a"]
        assert runtime.registry.get_plugin("com.example.b") is b_before
        assert b_before.plugin.loads == 1 and b_before.plugin.unloads == 0
        a_after = runtime.registry.get_plugin("com.example.a")
        assert a_after is not None and a_after is not a_before
        assert a_after.plugin.marker == "v2"
        assert a_after.manifest.version == "1.1.0"
        assert runtime.recent_reloads()[-1] is result
        assert result.as_dict()["duration_ms"] >= 0
    finally:
        runtime.shutdown()


def test_force_full_reload_fallback(tmp_path: Path, qapp):
    _dev, runtime = _write_pair(tmp_path)
    try:
        b_before = runtime.registry.get_plugin("com.example.b")
        result = runtime.reload_plugins(["com.example.a"], force_full=True)
        assert result.ok, result.message
        assert result.full_reload is True
        assert runtime.registry.get_plugin("com.example.b") is not b_before
    finally:
        runtime.shutdown()


def test_reload_provider_reloads_dependents_in_order(tmp_path: Path, qapp):
    _dev, runtime = _write_pair(tmp_path, dependent=True)
    try:
        assert runtime.affected_plugins(["com.example.a"]) == {
            "com.example.a",
            "com.example.b",
        }
        order = runtime._load_order({"com.example.a", "com.example.b"})
        assert order.index("com.example.a") < order.index("com.example.b")

        b_before = runtime.registry.get_plugin("com.example.b")
        result = runtime.reload_plugin("com.example.a", reason="update")
        assert result.ok, result.message
        assert result.affected == ["com.example.a", "com.example.b"]
        assert runtime.registry.get_plugin("com.example.b") is not b_before
    finally:
        runtime.shutdown()


def test_unload_provider_unloads_dependents(tmp_path: Path, qapp):
    _dev, runtime = _write_pair(tmp_path, dependent=True)
    try:
        result = runtime.unload_plugins(["com.example.a"], reason="disable")
        assert result.ok, result.message
        assert result.affected == ["com.example.a", "com.example.b"]
        assert runtime.registry.get_plugin("com.example.a") is None
        assert runtime.registry.get_plugin("com.example.b") is None
    finally:
        runtime.shutdown()


def test_selective_reload_rebuilds_events_services_and_settings(tmp_path: Path, qapp):
    from sllkgui.appcore import plugin_namespace, settings_registry

    dev = tmp_path / "dev"
    write_plugin(
        dev / "clean",
        plugin_id="com.example.clean",
        name="Clean",
        plugin_source=_CLEANUP_SOURCE,
    )
    runtime = _runtime(tmp_path, dev)
    runtime.bootstrap()
    try:
        old = runtime.registry.get_plugin("com.example.clean")
        assert old is not None
        probe = runtime.services.handle("test")
        old_service = probe.get("com.example.clean")
        assert old_service is old.plugin.service

        publisher = runtime.events.handle("test")
        publisher.publish("cleanup.topic")
        assert old.plugin.event_hits == 1

        result = runtime.reload_plugin("com.example.clean", reason="update")
        assert result.ok, result.message
        new = runtime.registry.get_plugin("com.example.clean")
        assert new is not None and new is not old
        assert probe.get("com.example.clean") is new.plugin.service
        assert new.plugin.service is not old_service

        publisher.publish("cleanup.topic")
        assert old.plugin.event_hits == 1
        assert new.plugin.event_hits == 1

        namespace = plugin_namespace("com.example.clean")
        pages = settings_registry().pages(namespace)
        assert len(pages) == 1
    finally:
        runtime.shutdown()


def test_native_extension_blocks_hot_update_before_unload(tmp_path: Path, qapp):
    dev, runtime = _write_pair(tmp_path)
    try:
        (dev / "a" / "native.pyd").write_bytes(b"not-a-real-extension")
        before = runtime.registry.get_plugin("com.example.a")
        result = runtime.reload_plugin("com.example.a", reason="update")
        assert not result.ok
        assert result.code == "PLUGIN_RESTART_REQUIRED"
        assert runtime.registry.get_plugin("com.example.a") is before
    finally:
        runtime.shutdown()


def test_logger_prefix_tracks_new_version(tmp_path: Path, qapp):
    dev, runtime = _write_pair(tmp_path)
    try:
        write_plugin(
            dev / "a",
            plugin_id="com.example.a",
            name="A",
            version="2.0.0",
            plugin_source=_source("A", marker="v2"),
        )
        assert runtime.reload_plugin("com.example.a", reason="update").ok
        logger = logging.getLogger("sllkgui.plugin.com.example.a")
        prefixes = [getattr(handler, "_prefix", "") for handler in logger.handlers]
        assert "[plugin:com.example.a@2.0.0]" in prefixes
    finally:
        runtime.shutdown()


def test_preflight_failure_leaves_old_instance_running(tmp_path: Path, qapp):
    dev, runtime = _write_pair(tmp_path)
    try:
        before = runtime.registry.get_plugin("com.example.a")
        (dev / "a" / "sllkgui-plugin.yml").write_text(
            "schema: 1\napi: 2\nid: com.example.a\nname: A\nversion: 1.0.0\n",
            encoding="utf-8",
        )
        result = runtime.reload_plugin("com.example.a", reason="update")
        assert not result.ok
        assert runtime.registry.get_plugin("com.example.a") is before
    finally:
        runtime.shutdown()


def test_single_flight_rejects_concurrent_reload(tmp_path: Path, qapp):
    _dev, runtime = _write_pair(tmp_path)
    try:
        runtime._reloading = True
        result = runtime.reload_plugin("com.example.a", reason="update")
        assert not result.ok
        assert result.code == "PLUGIN_RELOAD_IN_PROGRESS"
        result = runtime.reload_plugins(["com.example.a"], force_full=True)
        assert not result.ok
        assert result.code == "PLUGIN_RELOAD_IN_PROGRESS"
    finally:
        runtime._reloading = False
        runtime.shutdown()


def test_window_keeps_page_when_preflight_fails(tmp_path: Path, qapp):
    from sllkgui.window import load_run

    dev = tmp_path / "dev"
    write_plugin(dev / "a", plugin_id="com.example.a", name="A", plugin_source=_source("A"))
    window = load_run(
        data_dir=tmp_path / "data",
        gallery_dir=tmp_path / "data" / "gallery",
        plugin_dirs=[dev],
        install_missing_deps=False,
        interactive=False,
        check_tools=False,
    )
    try:
        assert window.open_route("com.example.a/home")
        pages = window.ui.load_pages.pages
        page = pages.currentWidget()
        (dev / "a" / "sllkgui-plugin.yml").write_text(
            "schema: 1\napi: 2\nid: com.example.a\nname: A\nversion: 1.0.0\n",
            encoding="utf-8",
        )
        result = window.reload_plugin_in_place("com.example.a", reason="update")
        assert not result.ok
        assert pages.currentWidget() is page
        assert window.current_route() == "com.example.a/home"
    finally:
        window.runtime.shutdown()
        window.close()
        window.deleteLater()


def test_window_rolls_back_failed_update(tmp_path: Path, qapp):
    from sllkgui.gallery.state import InstalledPlugin
    from sllkgui.window import load_run

    dev = tmp_path / "dev"
    write_plugin(dev / "a", plugin_id="com.example.a", name="A", plugin_source=_source("A", marker="v1"))
    window = load_run(
        data_dir=tmp_path / "data",
        gallery_dir=tmp_path / "data" / "gallery",
        plugin_dirs=[dev],
        install_missing_deps=False,
        interactive=False,
        check_tools=False,
    )

    class _RollbackManager:
        def __init__(self) -> None:
            self.state = SimpleNamespace(
                plugins={
                    "com.example.a": InstalledPlugin(
                        plugin_id="com.example.a",
                        version="1.0.0",
                        enabled=True,
                    )
                }
            )
            self.calls = 0

        def rollback(self, plugin_id: str, *, hot_reload: bool = False):
            self.calls += 1
            write_plugin(
                dev / "a",
                plugin_id="com.example.a",
                name="A",
                plugin_source=_source("A", marker="v1"),
            )
            return {"id": plugin_id, "version": "1.0.0"}

    manager = _RollbackManager()
    window.runtime.manager = manager
    try:
        assert window.open_route("com.example.a/home")
        bad_source = _source("A", marker="v2").replace(
            "        self.loads += 1",
            "        raise RuntimeError('boom')",
        )
        write_plugin(
            dev / "a",
            plugin_id="com.example.a",
            name="A",
            version="1.1.0",
            plugin_source=bad_source,
        )
        result = window.reload_plugin_in_place("com.example.a", reason="update")
        assert not result.ok
        assert result.rollback == "files"
        assert manager.calls == 1
        record = window.runtime.registry.get_plugin("com.example.a")
        assert record is not None
        assert record.plugin.marker == "v1"
        assert window.current_route() == "com.example.a/home"
    finally:
        window.runtime.shutdown()
        window.close()
        window.deleteLater()


def test_window_preserves_unaffected_page_and_restores_target(tmp_path: Path, qapp):
    from PySide6.QtWidgets import QWidget

    from sllkgui.guis.windows.main_window.registry import ensure_registered_page
    from sllkgui.window import load_run

    dev = tmp_path / "dev"
    write_plugin(dev / "a", plugin_id="com.example.a", name="A", plugin_source=_source("A"))
    write_plugin(dev / "b", plugin_id="com.example.b", name="B", plugin_source=_source("B"))

    window = load_run(
        data_dir=tmp_path / "data",
        gallery_dir=tmp_path / "data" / "gallery",
        plugin_dirs=[dev],
        install_missing_deps=False,
        interactive=False,
        check_tools=False,
    )
    try:
        assert window.open_route("com.example.b/home")
        pages = window.ui.load_pages.pages
        assert ensure_registered_page(window, "page_native_plugin_store")
        store_page = pages.findChild(QWidget, "page_native_plugin_store")
        assert store_page is not None
        b_page = pages.currentWidget()
        b_page.setText("B-state")
        a_button = window.gallery_registry.get("com.example.a/home").button_id
        b_button = window.gallery_registry.get("com.example.b/home").button_id

        result = window.reload_plugin_in_place("com.example.a", reason="update")
        assert result.ok, result.message
        assert pages.currentWidget() is b_page
        assert b_page.text() == "B-state"
        assert window.current_route() == "com.example.b/home"
        assert pages.findChild(QWidget, "page_native_plugin_store") is store_page
        assert a_button in window.ui.left_menu._menu_buttons
        assert b_button in window.ui.left_menu._menu_buttons

        assert window.open_route("com.example.a/home")
        a_page = pages.currentWidget()
        a_page.setText("A-state")
        result = window.reload_plugin_in_place("com.example.a", reason="update")
        assert result.ok, result.message
        assert pages.currentWidget() is not a_page
        assert pages.currentWidget().text() == "A-state"
        assert window.current_route() == "com.example.a/home"

        result = window.reload_plugin_in_place("com.example.a", reason="disable", load=False)
        assert result.ok, result.message
        assert window.runtime.registry.get("com.example.a/home") is None
        assert window.current_route() != "com.example.a/home"
        assert pages.currentWidget() is not None
        assert a_button not in window.ui.left_menu._menu_buttons
        assert b_button in window.ui.left_menu._menu_buttons
    finally:
        window.runtime.shutdown()
        window.close()
        window.deleteLater()
