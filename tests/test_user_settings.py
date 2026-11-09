"""用户配置持久化测试：覆盖文件缺失、损坏、非法值与写入失败。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sllkgui.appcore import Language, get_theme_manager, user_settings
from sllkgui.guis.windows.main_window import setup_main_window as setup_window_module
from sllkgui.guis.windows.main_window.setup_main_window import SetupMainWindow


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
    # FIX-02: 普通场景首次回写的版本仍为 SCHEMA_VERSION，且写入字段完整
    assert content["schema_version"] == user_settings.SCHEMA_VERSION, "default write keeps SCHEMA_VERSION"
    assert {k: v for k, v in content.items() if k != "schema_version"} == {
        "theme_name": "bright",
        "language": "en_us",
        "menu_mode": "overlay",
        "startup_size": [1100, 700],
    }, "all clean fields must be persisted"
    assert user_settings.load_user_settings() == {
        "theme_name": "bright",
        "language": "en_us",
        "menu_mode": "overlay",
        "startup_size": [1100, 700],
    }


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


def test_restore_appearance_applies_and_syncs_panel():
    from sllkgui.guicore import acrylic_transparency, glass_strength, reset_appearance_overrides

    synced = {}

    class _Config:
        def set_appearance(self, transparency=None, strength=None):
            synced["transparency"] = transparency
            synced["strength"] = strength

    window = SimpleNamespace(ui=SimpleNamespace(theme_config=_Config()))
    try:
        applied = SetupMainWindow.restore_appearance(
            window,
            {"acrylic_transparency": 72, "glass_strength": 35},
        )
        assert applied
        assert acrylic_transparency() == 72
        assert glass_strength() == 35
        assert synced == {"transparency": 72, "strength": 35}
    finally:
        reset_appearance_overrides()


def test_background_fields_roundtrip():
    assert user_settings.save_user_settings(
        background_image="/tmp/wall.png",
        background_fit="fill",
        background_recent=["/tmp/a.png", "/tmp/b.png"],
    )

    assert user_settings.load_user_settings() == {
        "background_image": "/tmp/wall.png",
        "background_fit": "fill",
        "background_recent": ["/tmp/a.png", "/tmp/b.png"],
    }


def test_background_recent_deduplicates_and_limits():
    assert user_settings.save_user_settings(
        background_recent=["/a.png", "/a.png", "/b.png", "/c.png", "/d.png", "/e.png", "/f.png"],
    )
    assert user_settings.load_user_settings()["background_recent"] == [
        "/a.png",
        "/b.png",
        "/c.png",
        "/d.png",
        "/e.png",
    ]


def test_invalid_background_fit_is_ignored():
    assert not user_settings.save_user_settings(background_fit="cover")
    assert not user_settings.save_user_settings(background_image=123)


def test_missing_schema_version_is_treated_as_v1():
    _write(user_settings.user_settings_path(), "theme_name: bright\n")
    assert user_settings.load_user_settings() == {"theme_name": "bright"}


def test_future_schema_version_keeps_known_fields_and_warns(monkeypatch):
    messages: list[str] = []

    class _FakeLogger:
        @staticmethod
        def warning(message: str) -> None:
            messages.append(message)

    monkeypatch.setattr(user_settings, "Logger", _FakeLogger)
    _write(
        user_settings.user_settings_path(),
        "schema_version: 99\ntheme_name: bright\nfuture_key: value\n",
    )

    assert user_settings.load_user_settings() == {"theme_name": "bright"}
    assert any("高于当前" in message for message in messages)
    assert any("未支持字段" in message for message in messages)


def test_future_schema_version_roundtrip_preserves_version_and_unknown():
    """FIX-02: 高版本 user.yaml 回写后版本不降级、未知键不丢失。"""
    # FIX-02: 以 :292 的高版本场景为基础，追加一次回写验证完整往返。
    _write(
        user_settings.user_settings_path(),
        "schema_version: 99\ntheme_name: bright\nfuture_key: value\n",
    )
    assert user_settings.load_user_settings() == {"theme_name": "bright"}

    assert user_settings.save_user_settings(theme_name="eye"), "save must succeed"

    content = yaml.safe_load(user_settings.user_settings_path().read_text(encoding="utf-8"))
    assert content["schema_version"] == 99, "high schema_version must not be downgraded"
    assert content["future_key"] == "value", "unknown keys must be preserved"
    assert content["theme_name"] == "eye", "updated field must be written"

    user_settings.reset_user_settings_cache()
    assert user_settings.load_user_settings() == {"theme_name": "eye"}, "known-field read stays stable"


def test_write_atomic_uses_unique_temp_and_fsync(monkeypatch):
    """FIX-02: 每次回写使用唯一临时文件，并在 fsync 后原子替换。"""
    # FIX-02: 通过 spy 记录 os.replace / os.fsync 的调用与临时文件名。
    replaced: list[str] = []
    fsynced: list[int] = []
    real_replace = user_settings.os.replace
    real_fsync = user_settings.os.fsync

    def _spy_replace(src, dst):
        replaced.append(str(src))
        return real_replace(src, dst)

    def _spy_fsync(fd):
        fsynced.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(user_settings.os, "replace", _spy_replace)
    monkeypatch.setattr(user_settings.os, "fsync", _spy_fsync)

    assert user_settings.save_user_settings(theme_name="eye")
    assert user_settings.save_user_settings(language="en_us")

    assert len(replaced) == 2, "each save must replace once"
    assert len(fsynced) == 2, "each save must fsync once"
    assert replaced[0] != replaced[1], "temp file names must be unique"
    assert all(
        name.startswith(".user.yaml.") and name.endswith(".tmp")
        for name in (Path(item).name for item in replaced)
    ), "mkstemp prefix/suffix must be used"


def test_migrate_state_fills_v2_v3_defaults():
    """FIX-02: _migrate_state 显式记录 v1→v2→v3 并按需补齐 v3 背景默认值。"""
    # FIX-02: 直接调用内部迁移函数，验证跃迁记录、默认值补齐与「只补不删」。
    transitions: list[str] = []
    migrated = user_settings._migrate_state(
        {"theme_name": "eye", "background_image": "/x.png"},
        version=1,
        fill_defaults=True,
        transitions=transitions,
    )

    assert len(transitions) == 2, "v1->v2 and v2->v3 must be recorded"
    assert migrated["theme_name"] == "eye", "existing keys must be preserved"
    assert migrated["background_image"] == "/x.png", "existing keys must not be overwritten by defaults"
    assert migrated["background_fit"] == user_settings.BACKGROUND_FIT_MODES[0], "v3 default must be filled"
    assert migrated["background_recent"] == [], "v3 default must be filled"

    only_v3: list[str] = []
    from_v2 = user_settings._migrate_state({}, version=2, fill_defaults=True, transitions=only_v3)
    assert len(only_v3) == 1, "only v2->v3 transition applies for v2 input"
    assert set(from_v2) == set(user_settings.V3_BACKGROUND_DEFAULTS), "all v3 defaults must be filled"
    assert user_settings._migrate_state({"theme_name": "eye"}, version=1) == {
        "theme_name": "eye"
    }, "incremental read must not inject defaults"


def test_save_reports_fsync_failure(monkeypatch):
    """FIX-02: fsync 失败返回 False，日志保留具体异常且临时文件被清理。"""
    # FIX-02: 注入 fsync 的 OSError，验证失败可观测、无残留临时文件。
    messages: list[str] = []

    class _FakeLogger:
        @staticmethod
        def warning(message: str) -> None:
            messages.append(message)

    monkeypatch.setattr(user_settings, "Logger", _FakeLogger)

    def _boom(_fd):
        raise OSError("fsync failed")

    monkeypatch.setattr(user_settings.os, "fsync", _boom)

    assert not user_settings.save_user_settings(theme_name="bright"), "fsync failure must return False"
    assert any("OSError" in m and "fsync failed" in m for m in messages), "failure must be observable in log"
    assert not list(user_settings.user_settings_path().parent.glob(".user.yaml.*.tmp")), (
        "temp file must be cleaned up"
    )
