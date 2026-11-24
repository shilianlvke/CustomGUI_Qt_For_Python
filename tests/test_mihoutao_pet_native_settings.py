"""宠物设置页原生化与基座事件联动测试。"""

from __future__ import annotations

import pytest
import yaml

from sllkgui.appcore import settings_registry
from sllkgui.guicore.pet.controller import MihoutaoPetController
from sllkgui.guicore.pet.events import CMD_HOP, CMD_STATE, pet_bus, reset_pet_bus
from sllkgui.guicore.pet.settings import DEFAULTS, register_pet_page


@pytest.fixture(autouse=True)
def _isolate_user_settings(tmp_path, monkeypatch):
    """把基座用户配置固定到临时目录，避免写到开发者真实目录。"""
    from sllkgui.appcore import user_settings as us

    monkeypatch.setattr(us, "data_root", lambda: tmp_path)
    us.reset_user_settings_cache()
    yield
    us.reset_user_settings_cache()


def test_pet_page_is_native_core_page(qapp, tmp_path, monkeypatch):
    """宠物页是 core 原生页，出现在原生分类而不是插件栏。"""
    monkeypatch.setattr(
        "sllkgui.appcore.user_settings.user_settings_path",
        lambda: tmp_path / "settings" / "user.yaml",
    )
    register_pet_page(replace=True)
    page = settings_registry().page("pet", namespace="core")
    assert page is not None
    assert page.namespace == "core"
    assert {spec.key for section in page.sections for spec in section.items} == set(DEFAULTS)
    # 不存在 plugin.sllkgui.pet 命名空间
    assert settings_registry().page("pet", namespace="plugin.sllkgui.pet") is None


def test_pet_settings_persist_in_user_yaml(qapp, tmp_path, monkeypatch):
    """宠物偏好落 user.yaml 的 pet_* 键，保存后经 core 总线同步。"""
    user = tmp_path / "settings" / "user.yaml"
    monkeypatch.setattr("sllkgui.appcore.user_settings.user_settings_path", lambda: user)
    register_pet_page(replace=True)
    pet = MihoutaoPetController()
    pet.start()
    try:
        pet.set_setting("shape", "gem")
        pet.set_setting("size", 300)
        stored = yaml.safe_load(user.read_text(encoding="utf-8"))
        assert stored["pet_shape"] == "gem"
        assert stored["pet_size"] == 300
        assert MihoutaoPetController._load_from_store()["shape"] == "gem"
    finally:
        pet.shutdown()


def test_base_operations_publish_pet_events(qapp, tmp_path, monkeypatch):
    """基座操作按协议发布宠物事件，命名/载荷一致。"""
    monkeypatch.setattr(
        "sllkgui.appcore.user_settings.user_settings_path",
        lambda: tmp_path / "settings" / "user.yaml",
    )
    reset_pet_bus()
    from sllkgui.guis.windows.main_window.pet_bridge import (
        on_layout_changed,
        on_search_opened,
        on_settings_opened,
        on_theme_cycled,
    )

    seen = []
    handle = pet_bus().handle("observer")
    handle.subscribe(CMD_STATE, lambda topic, payload: seen.append((topic, payload)))
    handle.subscribe(CMD_HOP, lambda topic, payload: seen.append((topic, payload)))

    assert on_theme_cycled("dracula") is True
    assert on_settings_opened() is True
    assert on_search_opened() is True
    assert on_layout_changed("overlay") is True
    states = [payload["state"] for topic, payload in seen if topic == CMD_STATE]
    assert "happy" in states and "curious" in states and "searching" in states
    assert any(topic == CMD_HOP for topic, _ in seen)
    assert all(payload["from"] == "sllkgui.base" for _, payload in seen)
    assert all(payload["seq"] > 0 for _, payload in seen)


def test_pet_bridge_errors_do_not_break_base(qapp, monkeypatch):
    """事件总线异常时基座操作不被打断。"""
    from sllkgui.guis.windows.main_window import pet_bridge

    def broken_bus():
        raise RuntimeError("bus down")

    monkeypatch.setattr(pet_bridge, "pet_bus", broken_bus)
    assert pet_bridge.on_theme_cycled("default") is False
    assert pet_bridge.on_search_opened() is False
