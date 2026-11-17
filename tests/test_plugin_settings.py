"""插件设置能力：ctx.settings 的声明、读写、外部变更与卸载清理。"""

from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.appcore import (
    PluginSettingsBackend,
    Setting,
    SettingsPage,
    SettingsRegistry,
    SettingsSection,
    SettingsSession,
    SettingsStore,
    ensure_core_pages,
    plugin_namespace,
)
from sllkgui.gallery.context import GalleryContextImpl
from sllkgui.gallery.manifest import load_manifest
from sllkgui.gallery.store import GalleryStore


class _MemoryCore:
    def __init__(self) -> None:
        self.data: dict = {}

    def load(self) -> dict:
        return dict(self.data)

    def save(self, updates) -> bool:
        self.data.update(dict(updates))
        return True

    def path(self) -> Path:
        return Path("user.yaml")


@pytest.fixture
def context(tmp_path, monkeypatch):
    root = write_plugin(tmp_path / "plugin", plugin_id="com.example.settings", name="Settings Demo")
    manifest = load_manifest(root)
    registry = SettingsRegistry()
    ensure_core_pages(registry)
    store = SettingsStore(settings_dir=tmp_path / "settings", core=_MemoryCore())
    monkeypatch.setattr("sllkgui.gallery.settings.settings_registry", lambda: registry)
    monkeypatch.setattr("sllkgui.gallery.settings.settings_store", lambda: store)
    ctx = GalleryContextImpl(manifest, GalleryStore(tmp_path / "gallery"))
    yield ctx, registry, store
    ctx.clear_settings()


def _page() -> SettingsPage:
    return SettingsPage(
        page_id="",
        title="桌面整理",
        sections=(
            SettingsSection(
                "behavior",
                (
                    Setting.switch("auto_refresh", True, "自动刷新"),
                    Setting.number("columns", 4, "列数", minimum=1, maximum=12),
                    Setting.select("sort_mode", "name", "排序方式", [("name", "名称"), ("time", "时间")]),
                ),
            ),
        ),
    )


def test_define_registers_namespaced_page(context):
    ctx, registry, _store = context
    ctx.settings.define(_page())
    pages = registry.pages(plugin_namespace("com.example.settings"))
    assert [page.page_id for page in pages] == ["com.example.settings"]
    assert pages[0].full_key("columns") == "plugin.com.example.settings.columns"


def test_get_set_and_reset(context):
    ctx, _registry, store = context
    ctx.settings.define(_page())
    assert ctx.settings.get("columns") == 4
    assert ctx.settings.get("auto_refresh") is True
    assert ctx.settings.get("missing", "fallback") == "fallback"

    assert ctx.settings.set("columns", 8)
    assert ctx.settings.get("columns") == 8
    assert "columns: 8" in store.path_for(ctx.settings.namespace).read_text(encoding="utf-8")

    assert not ctx.settings.set("columns", 99)
    assert ctx.settings.get("columns") == 8

    assert ctx.settings.reset("columns")
    assert ctx.settings.get("columns") == 4
    assert ctx.settings.values() == {"auto_refresh": True, "columns": 4, "sort_mode": "name"}


def test_external_save_notifies_plugin(context):
    ctx, registry, store = context
    ctx.settings.define(_page())
    received: list[tuple[str, object]] = []
    ctx.settings.on_changed(lambda key, value: received.append((key, value)))

    session = SettingsSession(registry, store)
    assert session.set("plugin.com.example.settings.sort_mode", "time")
    assert session.save()
    assert received == [("sort_mode", "time")]


def test_clear_removes_page_but_keeps_file(context):
    ctx, registry, store = context
    ctx.settings.define(_page())
    assert ctx.settings.set("columns", 9)
    path = store.path_for(ctx.settings.namespace)
    assert path.is_file()

    ctx.clear_settings()
    assert registry.pages(plugin_namespace("com.example.settings")) == ()
    assert path.is_file(), "卸载插件不应删除用户已经保存的配置"
    assert path.read_text(encoding="utf-8").find("columns: 9") >= 0


def test_plugin_files_are_separate_per_plugin(tmp_path):
    backend = PluginSettingsBackend(tmp_path)
    assert backend.save("com.example.one", {"columns": 3})
    assert backend.save("com.example.two", {"columns": 7})
    assert backend.load("com.example.one") == {"columns": 3}
    assert backend.load("com.example.two") == {"columns": 7}
