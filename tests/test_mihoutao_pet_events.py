"""桌面宠物事件总线与协议测试。"""

from __future__ import annotations

import pytest

from sllkgui.guicore.pet import events as ev
from sllkgui.guicore.pet.events import (
    CMD_HOP,
    CMD_SETTING,
    CMD_SHAPE,
    CMD_SPIN,
    CMD_STATE,
    EVENT_TYPES,
    EVT_READY,
    EVT_STATE_CHANGED,
    PetEventBus,
    is_valid_topic,
    pet_bus,
    reset_pet_bus,
)


@pytest.fixture
def bus():
    b = PetEventBus()
    yield b
    b.clear()


def test_topic_naming_and_registry():
    """命名规范：pet.<域>.<动作>，全部登记在 EVENT_TYPES。"""
    # 10 条保持型命令 + CMD_REACT 瞬态反应 + 6 条状态事件 = 17
    assert len(EVENT_TYPES) == 17
    for topic in EVENT_TYPES:
        assert topic.startswith("pet.")
        assert is_valid_topic(topic)
    assert is_valid_topic("pet.command.unknown") is False
    assert is_valid_topic("pet.event.unknown") is False


def test_publish_adds_from_and_seq(bus):
    """载荷强制带 from 与单调 seq。"""
    seen = []
    h = bus.handle("com.example.a")
    h.subscribe(CMD_SPIN, lambda topic, payload: seen.append((topic, payload)))
    assert h.publish(CMD_SPIN, {"extra": 1}) is True
    assert h.publish(CMD_SPIN, {"extra": 2}) is True
    assert [p["extra"] for _, p in seen] == [1, 2]
    assert all(p["from"] == "com.example.a" for _, p in seen)
    assert seen[0][1]["seq"] < seen[1][1]["seq"]


def test_subscribe_unsubscribe_is_idempotent(bus):
    """退订闭包幂等；clear_owner 只清自己的订阅。"""
    calls = []
    a = bus.handle("a")
    b = bus.handle("b")
    unsub = a.subscribe(CMD_HOP, lambda t, p: calls.append("a"))
    b.subscribe(CMD_HOP, lambda t, p: calls.append("b"))
    a.publish(CMD_HOP)
    assert calls == ["a", "b"]
    unsub()
    unsub()  # 幂等
    a.publish(CMD_HOP)
    assert calls == ["a", "b", "b"]
    a.clear()
    b.clear()
    a.publish(CMD_HOP)
    assert calls == ["a", "b", "b"]


def test_unknown_topic_and_missing_payload_rejected(bus):
    """未登记主题与缺必需载荷被拒，不分发、不抛异常。"""
    seen = []
    h = bus.handle("a")
    h.subscribe(CMD_STATE, lambda t, p: seen.append(p))
    assert h.publish("pet.command.nope", {}) is False
    assert h.publish(CMD_STATE, {}) is False
    assert isinstance(h.subscribe("pet.event.nope", lambda t, p: None), object)
    assert h.publish(CMD_STATE, {"state": "idle"}) is True
    assert len(seen) == 1


def test_subscriber_exception_isolated(bus):
    """单个订阅者异常不影响其它订阅者，也不回传给发布方。"""
    seen = []
    h = bus.handle("a")

    def bad(topic, payload):
        raise RuntimeError("boom")

    h.subscribe(CMD_SPIN, bad)
    h.subscribe(CMD_SPIN, lambda t, p: seen.append(p["seq"]))
    assert h.publish(CMD_SPIN) is True
    assert len(seen) == 1


def test_bus_singleton_and_reset():
    """进程级单例与测试重置。"""
    reset_pet_bus()
    a = pet_bus()
    assert pet_bus() is a
    b = reset_pet_bus()
    assert b is not a


def test_plugin_can_control_pet_via_events(qapp, tmp_path, monkeypatch):
    """插件经事件总线控制宠物，并观察状态变更。"""
    monkeypatch.setattr(
        "sllkgui.appcore.user_settings.user_settings_path",
        lambda: tmp_path / "settings" / "user.yaml",
    )
    reset_pet_bus()
    from sllkgui.guicore.pet import MihoutaoPetController

    pet = MihoutaoPetController()
    pet.start()
    try:
        plugin = pet_bus().handle("com.example.plugin")
        observed = []
        unsub = plugin.subscribe(EVT_STATE_CHANGED, lambda t, p: observed.append(p))

        before = pet.engine.spin.t
        assert plugin.publish(CMD_SPIN) is True
        assert pet.engine.spin.t == before + 360

        assert plugin.publish(CMD_STATE, {"state": "excited"}) is True
        assert pet.engine.state == "excited"
        assert observed and observed[-1]["state"] == "excited"
        assert observed[-1]["from"] == "sllkgui.base"

        assert plugin.publish(CMD_SHAPE, {"shape": "gem"}) is True
        assert pet.engine.shape_name == "gem"
        assert plugin.publish(CMD_SETTING, {"key": "deco_scale", "value": 1.5}) is True
        assert pet.engine.deco_scale == pytest.approx(1.5)
        unsub()
    finally:
        pet.shutdown()
    # shutdown 后命令无订阅者，发布成功但不再改变宠物
    assert pet.engine is None


def test_ready_event_on_start(qapp, tmp_path, monkeypatch):
    """启动完成时发布 ready 事件，携带可见性。"""
    monkeypatch.setattr(
        "sllkgui.appcore.user_settings.user_settings_path",
        lambda: tmp_path / "settings" / "user.yaml",
    )
    reset_pet_bus()
    from sllkgui.guicore.pet import MihoutaoPetController

    seen = []
    pet_bus().handle("observer").subscribe(EVT_READY, lambda t, p: seen.append(p))
    pet = MihoutaoPetController()
    pet.start()
    try:
        assert len(seen) == 1
        assert "visible" in seen[0]
        assert seen[0]["from"] == "sllkgui.base"
    finally:
        pet.shutdown()


def test_all_command_constants_covered():
    """所有命令常量都登记为合法类型。"""
    command_names = [name for name in dir(ev) if name.startswith("CMD_")]
    assert len(command_names) == 11
    for name in command_names:
        assert getattr(ev, name) in EVENT_TYPES
    event_names = [name for name in dir(ev) if name.startswith("EVT_")]
    assert len(event_names) == 6
    for name in event_names:
        assert getattr(ev, name) in EVENT_TYPES
