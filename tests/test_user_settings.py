"""用户配置持久化测试：覆盖文件缺失、损坏、非法值与写入失败。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml

from customgui.appcore import Language, get_theme_manager, user_settings
from customgui.guis.windows.main_window import setup_main_window as setup_window_module
from customgui.guis.windows.main_window.setup_main_window import SetupMainWindow


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """把用户配置固定到临时目录，避免读写开发者真实数据目录。"""
    monkeypatch.setattr(user_settings, "data_root", lambda: tmp_path)
    user_settings.reset_user_settings_cache()
    yield
    user_settings.reset_user_settings_cache()


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_missing_file_returns_empty():
    assert user_settings.load_user_settings() == {}


def test_save_then_load_roundtrip():
    assert user_settings.save_user_settings(
        theme_name="bright",
        language="en_us",
        menu_mode="overlay",
        startup_size=[1100, 700],
    )

    path = user_settings.user_settings_path()
    assert path == user_settings.data_root() / "settings" / "user.yaml"
    assert path.is_file()
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert content == {
        "theme_name": "bright",
        "language": "en_us",
        "menu_mode": "overlay",
        "startup_size": [1100, 700],
    }
    assert user_settings.load_user_settings() == content


def test_partial_save_merges_existing_keys():
    user_settings.save_user_settings(theme_name="eye")
    user_settings.save_user_settings(language="ja_jp")

    assert user_settings.load_user_settings() == {"theme_name": "eye", "language": "ja_jp"}


def test_corrupt_yaml_falls_back_and_can_recover():
    path = user_settings.user_settings_path()
    _write(path, "theme_name: [unclosed\n")

    assert user_settings.load_user_settings() == {}

    assert user_settings.save_user_settings(theme_name="bright")
    assert user_settings.load_user_settings() == {"theme_name": "bright"}


def test_non_mapping_top_level_is_ignored():
    _write(user_settings.user_settings_path(), "- theme_name\n- language\n")
    assert user_settings.load_user_settings() == {}


def test_invalid_fields_are_ignored_on_read():
    _write(
        user_settings.user_settings_path(),
        "theme_name: 123\nlanguage: ''\nmenu_mode: unsupported\nstartup_size: [0, 700]\n",
    )
    assert user_settings.load_user_settings() == {}


def test_invalid_values_are_not_written():
    assert not user_settings.save_user_settings(theme_name="")
    assert not user_settings.save_user_settings(startup_size=[0, 10])
    assert not user_settings.save_user_settings(menu_mode="unknown")
    assert not user_settings.save_user_settings(acrylic_transparency=-5)
    assert not user_settings.save_user_settings(glass_strength=101)
    assert not user_settings.user_settings_path().exists()


def test_appearance_fields_roundtrip():
    assert user_settings.save_user_settings(acrylic_transparency=35, glass_strength=80)

    assert user_settings.load_user_settings() == {
        "acrylic_transparency": 35,
        "glass_strength": 80,
    }


def test_unsupported_key_is_ignored():
    assert not user_settings.save_user_settings(unknown="value")
    assert not user_settings.user_settings_path().exists()


def test_write_failure_is_swallowed(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(
        user_settings,
        "user_settings_path",
        lambda: blocked / "settings" / "user.yaml",
    )

    assert not user_settings.save_user_settings(theme_name="bright")
    # 落盘失败不影响当前会话的内存值，后续成功保存可重试
    assert user_settings.load_user_settings() == {"theme_name": "bright"}


def test_reset_cache_rereads_manual_edits():
    user_settings.save_user_settings(theme_name="bright")
    path = user_settings.user_settings_path()
    _write(path, "theme_name: eye\nlanguage: zh_tw\n")

    assert user_settings.load_user_settings() == {"theme_name": "bright"}
    user_settings.reset_user_settings_cache()
    assert user_settings.load_user_settings() == {"theme_name": "eye", "language": "zh_tw"}


def test_legacy_ui_state_is_migrated_on_first_load():
    _write(
        user_settings.data_root() / "ui_state.json",
        '{"theme": "bright", "language": "en_us", "window_size": [1000, 650]}',
    )

    assert user_settings.load_user_settings() == {
        "theme_name": "bright",
        "language": "en_us",
        "startup_size": [1000, 650],
    }
    assert user_settings.user_settings_path().is_file()


def test_existing_user_file_skips_legacy_migration():
    user_settings.save_user_settings(theme_name="eye")
    _write(user_settings.data_root() / "ui_state.json", '{"theme": "bright"}')
    user_settings.reset_user_settings_cache()

    assert user_settings.load_user_settings() == {"theme_name": "eye"}


def test_corrupt_legacy_state_is_ignored():
    _write(user_settings.data_root() / "ui_state.json", "{broken")
    assert user_settings.load_user_settings() == {}


def test_restore_ui_state_applies_user_config():
    user_settings.save_user_settings(
        theme_name="bright",
        language="en_us",
        menu_mode="overlay",
        startup_size=[1100, 700],
    )
    calls: dict = {}

    class Window:
        def __init__(self):
            self.ui = SimpleNamespace(
                window=SimpleNamespace(apply_style=lambda: calls.setdefault("style", True))
            )

        def resize(self, width, height):
            calls["size"] = (width, height)

    try:
        state = SetupMainWindow.restore_ui_state(Window())
        assert state["menu_mode"] == "overlay"
        assert get_theme_manager().current() == "bright"
        assert Language.current() == "en_us"
        assert calls["size"] == (1100, 700)
        assert calls.get("style")
    finally:
        get_theme_manager().apply("default")
        Language.apply("zh_cn")


def test_restore_menu_mode_syncs_drawer(monkeypatch):
    applied = []

    class _Functions:
        @staticmethod
        def set_menu_mode(window, mode):
            applied.append(mode)

    class _Config:
        def __init__(self):
            self.value = None

        def set_menu_mode(self, mode):
            self.value = mode

    config = _Config()
    window = SimpleNamespace(ui=SimpleNamespace(theme_config=config))
    monkeypatch.setattr(setup_window_module, "MainFunctions", _Functions)

    SetupMainWindow.restore_menu_mode(window, {"menu_mode": "overlay"})

    assert applied == ["overlay"]
    assert config.value == "overlay"


def test_restore_menu_mode_ignores_invalid_value(monkeypatch):
    class _Functions:
        @staticmethod
        def set_menu_mode(window, mode):  # pragma: no cover - 不应被调用
            raise AssertionError(mode)

    window = SimpleNamespace(ui=SimpleNamespace(theme_config=SimpleNamespace(set_menu_mode=lambda mode: None)))
    monkeypatch.setattr(setup_window_module, "MainFunctions", _Functions)

    SetupMainWindow.restore_menu_mode(window, {"menu_mode": "floating"})
