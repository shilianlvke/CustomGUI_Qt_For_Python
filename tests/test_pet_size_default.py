"""桌面宠物默认尺寸（100）与尺寸边界的回归测试。"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from sllkgui.appcore import SettingsSession, ensure_core_pages, user_settings
from sllkgui.appcore.settings.base import STORAGE_PET_SIZE
from sllkgui.guicore.pet.controller import MihoutaoPetController, _normalize
from sllkgui.guicore.pet.engine.core import MihoutaoEngine
from sllkgui.guicore.pet.pet_window import PetWindow
from sllkgui.guicore.pet.settings import DEFAULTS

PET_SIZE_KEY = "core.pet.size"


def _pet_size_spec():
    from sllkgui.appcore.settings.base import build_core_pages

    for page in build_core_pages():
        for section in page.sections:
            for spec in section.items:
                if spec.key == "size":
                    return spec
    raise AssertionError("宠物设置页缺少 size")


def _isolate_user_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "data_root", lambda: tmp_path)
    user_settings.reset_user_settings_cache()
    ensure_core_pages()


def test_default_pet_size_is_100_across_defaults_page_and_session(tmp_path, monkeypatch):
    """DEFAULTS、设置页声明、会话兜底三处必须同为 100，避免配置漂移。"""
    _isolate_user_settings(tmp_path, monkeypatch)

    assert DEFAULTS["size"] == 100
    spec = _pet_size_spec()
    assert spec.default == 100
    assert spec.minimum == 96
    assert spec.maximum == 480
    assert spec.storage_key == STORAGE_PET_SIZE
    assert SettingsSession().value(PET_SIZE_KEY) == 100


def test_existing_user_pet_size_wins_over_new_default(tmp_path, monkeypatch):
    """本地已写入 pet_size 时优先用户值；只有缺失时才用 100。"""
    _isolate_user_settings(tmp_path, monkeypatch)
    assert SettingsSession().value(PET_SIZE_KEY) == 100

    assert user_settings.save_user_settings(pet_size=300)
    user_settings.reset_user_settings_cache()

    assert SettingsSession().value(PET_SIZE_KEY) == 300


def test_pet_size_boundaries_are_clamped_without_crash():
    """0 夹到下限、极大值夹到上限，非法类型回落默认（None 表示沿用默认）。"""
    assert _normalize("size", 0, DEFAULTS["size"]) == 96
    assert _normalize("size", 9999, DEFAULTS["size"]) == 480
    assert _normalize("size", 100, DEFAULTS["size"]) == 100
    assert _normalize("size", True, DEFAULTS["size"]) is None
    assert _normalize("size", "100", DEFAULTS["size"]) is None


def test_pet_window_uses_100_by_default_and_live_resizes(qapp):
    """未显式传尺寸时窗口取 DEFAULTS；设置变更可实时重建画布。"""
    assert QApplication.instance() is not None
    window = PetWindow(MihoutaoEngine())
    try:
        assert window._body_size == 100
        assert window.width() == window._size == window.height()

        assert window.set_body_size(160) == 160
        assert window._body_size == 160
        assert window.width() == window._size

        # 边界：0 / 极大值都夹到设置页同一区间，不抛异常
        assert window.set_body_size(0) == 96
        assert window.set_body_size(9999) == 480
        assert window.set_body_size("bad") == 100
    finally:
        window.close()


def test_controller_syncs_size_changes_to_existing_window(qapp):
    """设置保存后控制器把新尺寸应用到既有窗口，无需重启宠物。"""
    pet = MihoutaoPetController()
    pet.engine = MihoutaoEngine()
    pet.window = PetWindow(pet.engine)
    pet.preferences = dict(DEFAULTS)
    pet.preferences.update(size=220, show_pet=False, pinned=False)
    try:
        pet._sync_all()
        assert pet.window._body_size == 220

        pet.preferences["size"] = 100
        pet._sync_all()
        assert pet.window._body_size == 100
    finally:
        pet.window.close()
        pet.window = None
