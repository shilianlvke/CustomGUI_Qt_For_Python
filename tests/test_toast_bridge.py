"""插件上下文 → UI 总线的桥接测试。

锁定三件事：``ctx.toast`` 真的落到 ``ToastBus``、锚点是顶层窗口、卸载即收敛。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.appcore.feedback import ToastAnchor, ToastCode, ToastLevel, ToastState
from sllkgui.gallery.api import NOOP_TOAST, PLUGIN_API_VERSION
from sllkgui.gallery.context import GalleryContextImpl
from sllkgui.gallery.manifest import PluginManifest
from sllkgui.gallery.store import GalleryStore
from sllkgui.gallery.toast import ToastRouter
from sllkgui.guicore.feedback import reset_toast_bus


@pytest.fixture
def window(qapp):
    from PySide6.QtWidgets import QWidget

    win = QWidget()
    win.resize(900, 600)
    win.show()
    yield win
    win.close()


@pytest.fixture
def bus(qapp, window):
    bus = reset_toast_bus()
    bus.set_sources(main=lambda: window, settings=lambda: None)
    yield bus
    bus.reset()


@pytest.fixture
def ctx(tmp_path: Path, bus) -> GalleryContextImpl:
    router = ToastRouter()
    router.bind(bus)
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    manifest = PluginManifest(
        schema=1,
        api=PLUGIN_API_VERSION,
        plugin_id="com.example.toast",
        name="Toast",
        version="1.0.0",
        entry="plugin.py",
        root=tmp_path,
        permissions=(),
    )
    context = GalleryContextImpl(manifest, store, toast=router)
    yield context
    context.clear_toast()


def test_context_without_router_returns_noop(tmp_path: Path):
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    manifest = PluginManifest(
        schema=1,
        api=PLUGIN_API_VERSION,
        plugin_id="com.example.plain",
        name="Plain",
        version="1.0.0",
        entry="plugin.py",
        root=tmp_path,
        permissions=(),
    )
    context = GalleryContextImpl(manifest, store)
    assert context.toast is NOOP_TOAST
    assert context.toast.show("x").result.code == str(ToastCode.NOOP)


def test_plugin_toast_reaches_bus(ctx, bus, window):
    handle = ctx.toast.show("已保存", level="success", channel="test", dedupe_key="save")
    assert handle.result.ok is True
    assert handle.result.toast_id in bus.active(scope="com.example.toast")
    record = bus._records[handle.toast_id]
    assert record.request.level is ToastLevel.SUCCESS
    assert record.anchor is window


def test_loading_resolves_same_toast(ctx, bus):
    handle = ctx.toast.loading("正在连接…", channel="net")
    assert bus.state_of(handle.toast_id) is ToastState.SHOWN
    handle.succeed("连接成功")
    record = bus._records[handle.toast_id]
    assert record.request.text == "连接成功"
    assert record.request.level is ToastLevel.SUCCESS
    # 仍只有一条，没有新增
    assert len([item for item in bus._records.values() if item.channel == "net"]) == 1


def test_clear_on_unload(ctx, bus):
    handle = ctx.toast.show("处理中", level="loading", life=0)
    ctx.clear_toast()
    assert bus.state_of(handle.toast_id) is ToastState.CLOSED
    assert bus.active(scope="com.example.toast") == ()
    assert handle.update(text="不应生效").code == str(ToastCode.PLUGIN_UNLOADED)


def test_anchor_settings_prefers_settings_window(qapp, bus, window):
    from PySide6.QtWidgets import QWidget

    settings = QWidget()
    settings.resize(800, 500)
    settings.show()
    bus.set_sources(main=lambda: window, settings=lambda: settings)
    try:
        result = bus.show(ToastAnchor.SETTINGS, _request("设置里的结果"))
        assert bus._records[result.toast_id].anchor is settings
    finally:
        settings.close()


def _request(text: str):
    from sllkgui.appcore.feedback import ToastRequest

    return ToastRequest(text=text, scope="base")
