"""插件级事件总线：订阅/发布、owner 隔离、异常隔离与卸载清理。"""

from __future__ import annotations

from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.events import PluginEventBus
from sllkgui.gallery.loader import load_plugin, unload_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore


def test_subscribe_and_publish_with_source():
    bus = PluginEventBus()
    received = []
    bus.handle("consumer").subscribe("topic", lambda topic, payload: received.append((topic, payload)))
    bus.handle("producer").publish("topic", {"id": 1})
    assert received == [("topic", {"from": "producer", "id": 1})]


def test_unsubscribe_is_idempotent():
    bus = PluginEventBus()
    received = []
    unsub = bus.handle("a").subscribe("t", lambda topic, payload: received.append(payload))
    bus.handle("b").publish("t")
    unsub()
    unsub()  # 幂等
    bus.handle("b").publish("t")
    assert len(received) == 1


def test_clear_owner_keeps_other_subscribers():
    bus = PluginEventBus()
    a_calls, b_calls = [], []
    bus.handle("a").subscribe("t", lambda topic, payload: a_calls.append(payload))
    bus.handle("b").subscribe("t", lambda topic, payload: b_calls.append(payload))
    bus.clear_owner("a")
    bus.handle("c").publish("t")
    assert a_calls == []
    assert len(b_calls) == 1


def test_callback_exception_is_isolated():
    bus = PluginEventBus()

    def bad(topic, payload):
        raise RuntimeError("boom")

    good = []
    bus.handle("bad").subscribe("t", bad)
    bus.handle("good").subscribe("t", lambda topic, payload: good.append(payload))
    bus.handle("src").publish("t")
    assert len(good) == 1


def test_subscribe_during_publish_is_safe():
    bus = PluginEventBus()
    received = []

    def late(topic, payload):
        bus.handle("late").subscribe("t", lambda t, p: received.append("new"))

    bus.handle("first").subscribe("t", late)
    # 回调中新增订阅不应死锁，也不应在本轮被触发
    bus.handle("src").publish("t")
    assert received == []
    bus.handle("src").publish("t")
    assert "new" in received


def test_clear_all():
    bus = PluginEventBus()
    received = []
    bus.handle("a").subscribe("t", lambda topic, payload: received.append(payload))
    bus.clear()
    bus.handle("b").publish("t")
    assert received == []


def test_unload_plugin_removes_its_subscriptions(tmp_path: Path):
    bus = PluginEventBus()
    root = write_plugin(tmp_path / "hello")
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    record = load_plugin(root, store, GalleryRegistry(), events=bus)
    assert record is not None

    received = []
    # 模拟基座侧观察者订阅插件所在主题（owner 为宿主，不应被插件卸载误清）
    bus.handle("host").subscribe("plugin.event", lambda topic, payload: received.append(payload))
    record.context.events.subscribe("plugin.event", lambda topic, payload: received.append(payload))

    bus.handle("src").publish("plugin.event", {"n": 1})
    assert len(received) == 2

    unload_plugin(record)  # 只清插件 owner 的订阅
    bus.handle("src").publish("plugin.event", {"n": 2})
    assert len(received) == 3  # 只剩宿主的订阅收到
