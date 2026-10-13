"""主题管理器测试（订阅/切换/遥测）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from AppCore import ColorPalette, ThemeManager, get_theme_manager
from AppCore.SYS.module.telemetry_module import read_recent_events


@pytest.fixture
def diagnostics_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


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


def test_subscribe_qobject_destroyed_signal_removes_listener(qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QWidget

    manager = ThemeManager()

    class _Widget(QWidget):
        def on_theme(self):
            pass

    widget = _Widget()
    manager.subscribe(widget.on_theme)
    assert len(manager._listeners) == 1

    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)  # 触发 destroyed 信号

    assert len(manager._listeners) == 0


def test_notify_removes_deleted_cpp_subscription(diagnostics_dir):
    """C++ 对象已销毁而 Python 包装仍存活时，兜底移除失效订阅且不刷警告。"""
    manager = ThemeManager()

    class _FakeWidget:
        destroyed = None  # 无 destroyed 信号（模拟连接失败场景）

        def on_theme(self):
            raise RuntimeError("Internal C++ object (CShowCard) already deleted.")

    fake = _FakeWidget()
    manager.subscribe(fake.on_theme)
    assert len(manager._listeners) == 1

    manager.apply("eye")  # 不应抛出，失效订阅被静默移除

    assert len(manager._listeners) == 0
