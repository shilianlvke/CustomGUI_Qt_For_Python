"""基座快捷键表：平台修饰键、作用域、优先级、冲突与清理。"""

from __future__ import annotations

import pytest

from sllkgui.guicore.shortcuts import (
    PRIORITY_BASE,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    ConflictPolicy,
    KeyBinding,
    Scope,
    ShortcutError,
    ShortcutRegistry,
)


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def registry(app):
    """每条用例独立的注册表：不污染进程内单例。"""
    table = ShortcutRegistry()
    yield table
    table.shutdown()


def _binding(sequence: str, platform: str = "win32") -> KeyBinding:
    return KeyBinding.parse(sequence, platform=platform)


def _hit(sink: list[str], value: str):
    def callback() -> None:
        sink.append(value)

    return callback


# ----------------------------------------------------------------------
# 解析与平台差异
# ----------------------------------------------------------------------
def test_primary_maps_to_platform_modifier():
    """primary 在 macOS 是 ⌘，在 Windows/Linux 是 Ctrl；底层 Qt 位一致。"""
    windows = _binding("primary+k", "win32")
    macos = _binding("primary+k", "darwin")
    linux = _binding("primary+k", "linux")
    assert windows.modifiers == macos.modifiers == linux.modifiers
    assert windows.display() == "Ctrl+K"
    assert linux.display() == "Ctrl+K"
    assert macos.display() == "⌘K"
    # 可移植文本与平台无关：配置文件在不同系统间可直接复用
    assert windows.sequence == macos.sequence == "primary+k"


def test_ctrl_and_meta_swap_on_macos():
    """Qt 在 macOS 上把 ⌘ 映射成 Control、把物理 Control 映射成 Meta。"""
    from PySide6.QtCore import Qt

    control = Qt.KeyboardModifier.ControlModifier.value
    meta = Qt.KeyboardModifier.MetaModifier.value
    ctrl_win = _binding("ctrl+p", "win32")
    ctrl_mac = _binding("ctrl+p", "darwin")
    meta_win = _binding("meta+p", "win32")
    meta_mac = _binding("meta+p", "darwin")

    assert ctrl_win.modifiers == control
    assert ctrl_mac.modifiers == meta
    assert meta_win.modifiers == meta
    assert meta_mac.modifiers == control
    # macOS 的 ⌘ 同时是 primary 与 meta：物理上是同一个键
    assert meta_mac.modifiers == _binding("primary+p", "darwin").modifiers
    assert ctrl_mac.display() == "⌃P"
    assert meta_mac.display() == "⌘P"


def test_modifier_order_is_normalized():
    assert _binding("shift+ctrl+p").sequence == "ctrl+shift+p"
    assert _binding("Shift + Control + P").sequence == "ctrl+shift+p"
    assert _binding("Primary + K").sequence == "primary+k"


def test_named_and_function_keys():
    assert _binding("escape").display() == "Esc"
    assert _binding("f12").display() == "F12"
    assert _binding("comma").key == _binding(",").key
    assert _binding("space").display() == "Space"


@pytest.mark.parametrize("sequence", ["", "   ", "ctrl+", "ctrl+a+b", "unknownkey", "+"])
def test_invalid_sequences_are_rejected(sequence):
    with pytest.raises(ShortcutError) as exc:
        KeyBinding.parse(sequence)
    assert exc.value.code == "SHORTCUT_INVALID_SEQUENCE"


def test_shifted_punctuation_matches_physical_key():
    """按住 Shift 时 Qt 报的是上档字符，绑定仍需命中物理键。"""
    binding = _binding("shift+slash")
    assert binding.matches(ord("/"), binding.modifiers)
    assert binding.matches(ord("?"), binding.modifiers)
    assert not binding.matches(ord("?"), 0)


# ----------------------------------------------------------------------
# 注册与派发
# ----------------------------------------------------------------------
def test_global_shortcut_activates_anywhere(registry):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    registry.register("demo.save", "primary+s", _hit(hits, "save"), owner="demo")
    binding = _binding("primary+s")

    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "demo.save"
    assert hits == ["save"]
    assert registry.is_installed() is True


def test_local_scope_only_matches_host_subtree(registry, app):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    host = QWidget()
    child = QWidget(host)
    outside = QWidget()
    registry.register(
        "demo.local",
        "f9",
        _hit(hits, "local"),
        owner="demo",
        scope=Scope.LOCAL,
        host=host,
    )
    binding = _binding("f9")

    assert registry.activate(binding.key, binding.modifiers, child) == "demo.local"
    assert registry.activate(binding.key, binding.modifiers, outside) is None
    assert registry.activate(binding.key, binding.modifiers, None) is None
    assert hits == ["local"]


def test_local_scope_requires_host(registry):
    with pytest.raises(ShortcutError) as exc:
        registry.register("demo.bad", "f9", lambda: None, owner="demo", scope="local")
    assert exc.value.code == "SHORTCUT_INVALID_SEQUENCE"


def test_priority_wins_and_lower_entry_takes_over_when_disabled(registry):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    binding = _binding("primary+j")
    high = registry.register(
        "base.high",
        "primary+j",
        _hit(hits, "high"),
        owner="base",
        priority=PRIORITY_BASE,
        locked=True,
    )
    registry.register(
        "plugin.low",
        "primary+j",
        _hit(hits, "low"),
        owner="plugin",
        priority=PRIORITY_LOW,
        policy=ConflictPolicy.SHADOW,
    )

    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "base.high"
    high.set_enabled(False)
    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "plugin.low"
    assert hits == ["high", "low"]


# ----------------------------------------------------------------------
# 冲突检测
# ----------------------------------------------------------------------
def test_conflict_rejected_by_default(registry):
    registry.register("a.one", "primary+k", lambda: None, owner="a")
    with pytest.raises(ShortcutError) as exc:
        registry.register("b.one", "primary+k", lambda: None, owner="b")
    assert exc.value.code == "SHORTCUT_CONFLICT"
    assert "a.one" in exc.value.detail
    # 拒绝是原子的：失败条目没有留下任何痕迹
    assert registry.count() == 1


def test_locked_binding_cannot_be_replaced(registry):
    registry.register("base.search", "primary+k", lambda: None, owner="base", locked=True)
    with pytest.raises(ShortcutError) as exc:
        registry.register("plugin.search", "primary+k", lambda: None, owner="plugin", policy="replace")
    assert exc.value.code == "SHORTCUT_LOCKED"
    assert [item.shortcut_id for item in registry.describe()] == ["base.search"]


def test_replace_policy_takes_over(registry):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    binding = _binding("f7")
    registry.register("a.one", "f7", _hit(hits, "a"), owner="a")
    registry.register("b.one", "f7", _hit(hits, "b"), owner="b", policy="replace")

    assert registry.count() == 1
    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "b.one"
    assert hits == ["b"]


def test_conflicts_are_reported_with_winner(registry):
    binding = _binding("primary+k")
    registry.register("base.search", "primary+k", lambda: None, owner="base", priority=PRIORITY_BASE, locked=True)
    registry.register(
        "plugin.k",
        "primary+k",
        lambda: None,
        owner="plugin",
        priority=PRIORITY_LOW,
        policy="shadow",
    )
    conflicts = registry.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].sequence == binding.sequence
    assert conflicts[0].winner == "base.search"
    assert set(conflicts[0].owners) == {"base", "plugin"}


def test_same_chord_in_disjoint_windows_is_not_a_conflict(registry, app):
    from PySide6.QtWidgets import QWidget

    first, second = QWidget(), QWidget()
    registry.register("a.one", "f8", lambda: None, owner="a", scope="local", host=first)
    registry.register("b.one", "f8", lambda: None, owner="b", scope="local", host=second)
    assert registry.count() == 2
    assert registry.conflicts() == ()


def test_conflict_detection_uses_physical_chord(app):
    """文本不同但物理组合相同的绑定必须判为冲突。"""
    windows = ShortcutRegistry(platform="win32")
    darwin = ShortcutRegistry(platform="darwin")
    try:
        windows.register("a.one", "primary+k", lambda: None, owner="a")
        with pytest.raises(ShortcutError) as exc:
            windows.register("b.one", "ctrl+k", lambda: None, owner="b")
        assert exc.value.code == "SHORTCUT_CONFLICT"

        darwin.register("a.one", "primary+k", lambda: None, owner="a")
        with pytest.raises(ShortcutError) as exc:
            darwin.register("b.one", "meta+k", lambda: None, owner="b")
        assert exc.value.code == "SHORTCUT_CONFLICT"
        # macOS 上物理 Control 是另一个键，不构成冲突
        darwin.register("c.one", "ctrl+k", lambda: None, owner="c")
        assert darwin.count() == 2
    finally:
        windows.shutdown()
        darwin.shutdown()


def test_reregister_same_id_replaces_without_self_conflict(registry):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    binding = _binding("primary+o")
    registry.register("demo.one", "primary+o", _hit(hits, "v1"), owner="demo")
    registry.register("demo.one", "primary+o", _hit(hits, "v2"), owner="demo")

    assert registry.count() == 1
    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "demo.one"
    assert hits == ["v2"]


def test_reregister_rebinds_lifecycle_to_new_host(registry, app):
    """换宿主重注册后，旧宿主销毁不得误删新条目。"""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QWidget

    old_host, new_host = QWidget(), QWidget()
    registry.register("demo.local", "f9", lambda: None, owner="demo", scope="local", host=old_host)
    registry.register("demo.local", "f9", lambda: None, owner="demo", scope="local", host=new_host)

    old_host.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert registry.count() == 1

    new_host.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert registry.count() == 0


def test_update_sequence_rechecks_conflict_and_keeps_old(registry):
    registry.register("a.one", "f5", lambda: None, owner="a")
    registry.register("b.one", "f6", lambda: None, owner="b")

    with pytest.raises(ShortcutError) as exc:
        registry.update("b.one", sequence="f5")
    assert exc.value.code == "SHORTCUT_CONFLICT"
    # 冲突时保留原序列，不让条目进入半更新状态
    assert registry.get("b.one").sequence == "f6"


# ----------------------------------------------------------------------
# 启用 / 禁用 / 注销
# ----------------------------------------------------------------------
def test_registry_switch_and_entry_toggle(registry):
    from PySide6.QtWidgets import QWidget

    hits: list[str] = []
    handle = registry.register("demo.toggle", "f10", _hit(hits, "hit"), owner="demo")
    binding = _binding("f10")

    handle.set_enabled(False)
    assert registry.activate(binding.key, binding.modifiers, QWidget()) is None
    handle.set_enabled(True)
    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "demo.toggle"

    registry.set_active(False)
    assert registry.activate(binding.key, binding.modifiers, QWidget()) is None
    registry.set_active(True)
    assert registry.activate(binding.key, binding.modifiers, QWidget()) == "demo.toggle"
    assert hits == ["hit", "hit"]


def test_unregister_owner_and_shutdown(registry):
    registry.register("a.one", "f1", lambda: None, owner="a")
    registry.register("a.two", "f2", lambda: None, owner="a")
    registry.register("b.one", "f3", lambda: None, owner="b")

    assert registry.unregister_owner("a") == 2
    assert registry.count() == 1
    assert registry.unregister("b.one") is True
    assert registry.unregister("b.one") is False

    registry.shutdown()
    assert registry.count() == 0
    assert registry.is_installed() is False


def test_host_destruction_releases_binding(registry, app):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    registry.register("demo.local", "f9", lambda: None, owner="demo", scope="local", host=host)
    assert registry.count() == 1

    host.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert registry.count() == 0


def test_callback_errors_are_isolated(registry):
    def boom() -> None:
        raise RuntimeError("boom")

    registry.register("demo.boom", "f4", boom, owner="demo")
    binding = _binding("f4")
    assert registry.activate(binding.key, binding.modifiers) == "demo.boom"  # 不向上抛


# ----------------------------------------------------------------------
# 事件过滤器
# ----------------------------------------------------------------------
def test_event_filter_consumes_key_and_skips_text_input(registry, app):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QLineEdit, QWidget

    hits: list[str] = []
    registry.register("demo.save", "primary+s", _hit(hits, "save"), owner="demo")
    registry.register("demo.plain", "a", _hit(hits, "plain"), owner="demo")

    window = QWidget()
    window.show()
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier, "s")
    app.sendEvent(window, event)
    assert hits == ["save"]
    assert event.isAccepted() is True

    editor = QLineEdit()
    editor.show()
    plain = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
    app.sendEvent(editor, plain)
    # 编辑文本时纯字符键必须留给输入框
    assert hits == ["save"]

    with_modifier = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier, "s")
    app.sendEvent(editor, with_modifier)
    assert hits == ["save", "save"]


def test_unmatched_keys_are_not_consumed(registry, app):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QWidget

    registry.register("demo.save", "primary+s", lambda: None, owner="demo")
    window = QWidget()
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.NoModifier, "q")
    app.sendEvent(window, event)
    assert event.isAccepted() is False


def test_describe_exposes_display_and_metadata(registry):
    registry.register(
        "demo.one",
        "primary+shift+p",
        lambda: None,
        owner="demo",
        priority=PRIORITY_NORMAL,
        description="切换面板",
    )
    (info,) = registry.describe(owner="demo")
    assert info.shortcut_id == "demo.one"
    assert info.sequence == "primary+shift+p"
    assert info.display == "Ctrl+Shift+P"
    assert info.scope == "global"
    assert info.priority == PRIORITY_NORMAL
    assert info.description == "切换面板"
