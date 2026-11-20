"""插件服务注册表：注册/解析、owner-token 隔离、卸载清理。"""

from __future__ import annotations

from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.loader import load_plugin, unload_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.services import PluginServiceRegistry
from sllkgui.gallery.store import GalleryStore


def test_register_resolve_and_default_name():
    reg = PluginServiceRegistry()
    svc = object()
    handle = reg.handle("com.example.a")
    assert handle.register(svc) is True
    assert handle.get("com.example.a") is svc
    assert handle.has("com.example.a") is True
    assert handle.get("missing") is None


def test_impersonation_rejected():
    reg = PluginServiceRegistry()
    assert reg.handle("a").register(object(), name="b") is False
    assert reg.handle("b").get("b") is None


def test_duplicate_name_other_owner_rejected():
    """重名异主在注册表层被拒（handle 层的冒名已在另一测试覆盖）。"""
    reg = PluginServiceRegistry()
    assert reg._register("shared", "first", "a") is True
    assert reg._register("shared", "second", "b") is False
    assert reg._get("shared") == "first"


def test_unregister_only_own_service():
    reg = PluginServiceRegistry()
    reg.handle("a").register("a-svc")  # 名字 = owner "a"
    reg.handle("b").unregister("a")  # 不是 owner，无效
    assert reg.handle("b").get("a") == "a-svc"
    reg.handle("a").unregister("a")
    assert reg.handle("b").get("a") is None


def test_clear_owner_keeps_others():
    reg = PluginServiceRegistry()
    reg.handle("a").register("a-svc")
    reg.handle("b").register("b-svc")
    reg.clear_owner("a")
    assert reg.handle("b").get("a") is None
    assert reg.handle("b").get("b") == "b-svc"


def test_clear_all():
    reg = PluginServiceRegistry()
    reg.handle("a").register("a-svc", name="svc")
    reg.clear()
    assert reg.handle("b").get("svc") is None


def test_unload_plugin_removes_its_services(tmp_path: Path):
    reg = PluginServiceRegistry()
    root = write_plugin(tmp_path / "provider")
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    record = load_plugin(root, store, GalleryRegistry(), services=reg)
    assert record is not None

    record.context.services.register("data-source")
    assert reg.handle("other").get("com.example.hello") == "data-source"

    unload_plugin(record)
    assert reg.handle("other").get("com.example.hello") is None
