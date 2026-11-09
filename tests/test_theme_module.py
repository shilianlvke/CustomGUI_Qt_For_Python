"""主题管理器测试（订阅/切换/遥测）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from sllkgui.appcore import ColorPalette, ThemeManager, get_theme_manager
from sllkgui.appcore.sysx.modules.telemetry_module import read_recent_events


@pytest.fixture
def diagnostics_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(tmp_path))
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
    # FIX-07: 失效的 WeakMethod 引用须被 _notify 清理，不再滞留在订阅列表
    assert len(manager._listeners) == 0, "dead weak method must be pruned from listeners"


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


def test_unsubscribe_removes_bound_method(diagnostics_dir):
    """FIX-07: 绑定方法可正常退订（WeakMethod 改用等价比较）。"""
    # FIX-07: 原实现用 is 比较 WeakMethod() 结果，恒 False，绑定方法退订不掉。
    manager = ThemeManager()
    calls: list[str] = []

    class _Widget:
        def on_theme(self):
            calls.append("bound")

    widget = _Widget()
    callback = widget.on_theme
    manager.subscribe(callback)
    assert len(manager._listeners) == 1

    manager.unsubscribe(callback)
    assert len(manager._listeners) == 0, "bound method must be removed by equality"

    manager.apply("bright")
    assert calls == [], "unsubscribed callback must not be notified"


def test_notify_prunes_dead_weakmethod(diagnostics_dir):
    """FIX-07: _notify 遍历后清理失效弱引用，订阅列表不单调增长。"""
    # FIX-07: 失效 WeakMethod 不再只 continue，须从 _listeners 移除。
    import gc

    manager = ThemeManager()

    class _Widget:
        def on_theme(self):
            pass

    widget = _Widget()
    manager.subscribe(widget.on_theme)
    assert len(manager._listeners) == 1

    del widget
    gc.collect()
    manager.apply("bright")
    assert len(manager._listeners) == 0, "dead weak references must be pruned"


def test_apply_is_reentrant_under_concurrent_notify(diagnostics_dir):
    """FIX-07: 并发 apply/cycle 与锁内读不死锁、不抛异常。"""
    # FIX-07: RLock + 锁外回调，回调里再取同一把锁的 current() 不应死锁。
    import threading

    manager = ThemeManager()
    errors: list[Exception] = []
    barrier = threading.Barrier(4)

    def _on_theme():
        # 订阅回调在锁外执行：这里再次获取同一把锁不应死锁
        manager.current()

    manager.subscribe(_on_theme)

    def _worker():
        try:
            barrier.wait(timeout=5)
            for _ in range(20):
                manager.apply("eye")
                manager.cycle()
                manager.current()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, daemon=True) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads), "apply/cycle must not deadlock"
    assert errors == [], f"concurrent apply raised: {errors}"
