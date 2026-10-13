"""主题管理器测试（订阅/切换/遥测）。"""

import pytest

from AppCore import ColorPalette, ThemeManager, get_theme_manager
from AppCore.SYS.module.telemetry_module import read_recent_events


@pytest.fixture
def diagnostics_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def _restore_theme():
    yield
    get_theme_manager().apply("default")


def test_theme_manager_singleton():
    assert get_theme_manager() is get_theme_manager()


def test_apply_updates_palette_and_records_event(diagnostics_dir):
    manager = ThemeManager()
    before = ColorPalette.custom_bg_one

    manager.apply("eye")

    assert manager.current() == "eye"
    events = [e for e in read_recent_events(limit=5) if e["name"] == "ui.theme_switch"]
    assert events and events[-1]["payload"]["theme"] == "eye"
    # 恢复默认主题（不同主题色应不同）
    manager.apply("default")
    assert ColorPalette.custom_bg_one == before


def test_cycle_follows_sequence(diagnostics_dir):
    manager = ThemeManager()
    manager.apply("default")

    assert manager.cycle() == "eye"
    assert manager.cycle() == "bright"
    assert manager.cycle() == "default"


def test_apply_unknown_theme_raises():
    manager = ThemeManager()
    with pytest.raises(ValueError, match="未知主题"):
        manager.apply("nonexistent")


def test_subscribe_notifies_bound_method_and_function(diagnostics_dir):
    manager = ThemeManager()
    calls = []

    class _Widget:
        def on_theme(self):
            calls.append("bound")

    widget = _Widget()
    manager.subscribe(widget.on_theme)

    def _listener():
        calls.append("function")

    manager.subscribe(_listener)

    manager.apply("bright")
    assert sorted(calls) == ["bound", "function"]


def test_subscribe_weak_method_auto_removed(diagnostics_dir):
    manager = ThemeManager()
    calls = []

    class _Widget:
        def on_theme(self):
            calls.append("bound")

    widget = _Widget()
    manager.subscribe(widget.on_theme)
    manager.apply("bright")
    assert "bound" in calls

    calls.clear()
    del widget  # 组件销毁后订阅自动失效（弱引用）
    manager.apply("default")
    assert "bound" not in calls
