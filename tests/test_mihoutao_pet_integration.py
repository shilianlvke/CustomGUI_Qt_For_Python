"""桌面宠物与基座基础能力的统一接入测试。"""

from __future__ import annotations

import pytest

from sllkgui.guicore.pet.engine.core import MihoutaoEngine


def test_pet_settings_page_schema(qapp):
    """设置页挂在 plugin 命名空间，覆盖展示/外观两组共 7 项。"""
    from sllkgui.guicore.pet.settings import PET_NAMESPACE, build_pet_page

    page = build_pet_page()
    assert page.namespace == PET_NAMESPACE
    assert page.page_id == "pet"
    keys = [spec.key for section in page.sections for spec in section.items]
    assert set(keys) == {
        "show_pet",
        "pinned",
        "follow_pointer",
        "shape",
        "color",
        "size",
        "deco_scale",
    }
    assert all(spec.label_key.startswith("language.UI.ui_Pet") for spec in page.specs())


def test_pet_shortcuts_register_and_unregister(qapp):
    """快捷键走基座注册表，owner 隔离，关闭后无残留。"""
    from sllkgui.guicore.pet.shortcuts import PET_BINDINGS, PET_OWNER, install_pet_shortcuts, uninstall_pet_shortcuts
    from sllkgui.guicore.shortcuts import shortcut_registry

    class Actions:
        def toggle(self):
            pass

        def spin(self):
            pass

        def hop(self):
            pass

        def burst(self):
            pass

    installed = install_pet_shortcuts(Actions())
    assert len(installed) == len(PET_BINDINGS)
    assert shortcut_registry().count(PET_OWNER) == len(PET_BINDINGS)
    details = {item.shortcut_id: item for item in shortcut_registry().describe(owner=PET_OWNER)}
    assert details["pet.toggle"].owner == PET_OWNER
    assert details["pet.toggle"].description
    # 幂等：重复安装不会叠加
    install_pet_shortcuts(Actions())
    assert shortcut_registry().count(PET_OWNER) == len(PET_BINDINGS)
    assert uninstall_pet_shortcuts() == len(PET_BINDINGS)
    assert shortcut_registry().count(PET_OWNER) == 0


def test_pet_shortcut_conflict_does_not_break(qapp):
    """占用宠物快捷键序列不会抛异常，冲突项被跳过且可查。"""
    from sllkgui.guicore.pet.settings import register_pet_page
    from sllkgui.guicore.pet.shortcuts import PET_BINDINGS, install_pet_shortcuts, uninstall_pet_shortcuts
    from sllkgui.guicore.shortcuts import ConflictPolicy, shortcut_registry

    register_pet_page(replace=True)
    registry = shortcut_registry()
    seq = PET_BINDINGS[0][1]
    registry.register("test.pet.occupy", seq, lambda: None, owner="test.other", policy=ConflictPolicy.ERROR)

    class Actions:
        def toggle(self):
            pass

        def spin(self):
            pass

        def hop(self):
            pass

        def burst(self):
            pass

    installed = install_pet_shortcuts(Actions())
    assert "pet.toggle" not in installed
    assert len(installed) == len(PET_BINDINGS) - 1
    assert (
        any(conflict.sequence == seq for conflict in registry.conflicts()) is False
    )  # ERROR 策略拒绝注册，不产生共存冲突
    uninstall_pet_shortcuts()
    registry.unregister("test.pet.occupy")


def test_pet_language_keys():
    """四种语言都提供宠物键，切换语言后文案键可解析。"""
    from sllkgui.appcore import AppLanguages

    expected = 33
    for locale in ("zh_cn", "zh_tw", "en_us", "ja_jp"):
        table = AppLanguages[locale].data
        ui = table.get("UI", {})
        keys = [key for key in ui if key.startswith("ui_Pet")]
        assert len(keys) == expected, locale
    assert AppLanguages["en_us"].data["UI"]["ui_PetSettingsTitle"] == "Mihoutao Desktop Pet"


def test_pet_accent_color(qapp):
    """主题强调色覆盖默认 ring，但状态显式 ring 保持原型配色。"""
    engine = MihoutaoEngine()
    engine.set_accent_color("#ff0000")
    engine.set_state("idle")
    engine.update(0.016)
    assert "#ff0000" in engine.render_svg()
    engine.set_state("angry")
    engine.update(0.016)
    assert "#E0574B" in engine.render_svg()  # 原型显式配色不被覆盖
    engine.set_accent_color(None)
    assert engine.accent_color is None


def test_controller_settings_bus_sync(qapp, tmp_path, monkeypatch):
    """设置保存后经 change bus 即时同步到引擎，无需重启宠物。"""
    from sllkgui.appcore import settings_change_bus
    from sllkgui.guicore.pet import MihoutaoPetController
    from sllkgui.guicore.pet.settings import PET_NAMESPACE, register_pet_page

    monkeypatch.setattr("sllkgui.appcore.user_settings.user_settings_path", lambda: tmp_path / "settings" / "user.yaml")
    register_pet_page(replace=True)
    pet = MihoutaoPetController()
    pet.start()
    try:
        assert pet.engine is not None
        settings_change_bus().publish(PET_NAMESPACE, {"shape": "gem", "deco_scale": 1.5})
        assert pet.engine.shape_name == "gem"
        assert pet.engine.deco_scale == pytest.approx(1.5)
    finally:
        pet.shutdown()
    assert pet._unsub_settings is None
