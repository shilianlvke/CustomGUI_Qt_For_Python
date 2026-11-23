"""Toast 总线测试：去重、通道、溢出、状态机、线程与清理。

用真实 ``CToast`` 渲染（offscreen），但断言总线状态而不是像素；视觉行为由
``tests/test_feedback_components.py`` 与人工验收覆盖。
"""

from __future__ import annotations

import pytest

from sllkgui.appcore.feedback import (
    DedupePolicy,
    ToastAnchor,
    ToastCode,
    ToastDismiss,
    ToastDismissReason,
    ToastLevel,
    ToastMode,
    ToastRequest,
    ToastState,
)


@pytest.fixture
def bus(qapp):
    from sllkgui.guicore.feedback import reset_toast_bus

    bus = reset_toast_bus()
    yield bus
    bus.reset()


@pytest.fixture
def window(qapp, bus):
    from PySide6.QtWidgets import QWidget

    win = QWidget()
    win.resize(900, 600)
    win.show()
    bus.set_sources(main=lambda: win, settings=lambda: None)
    yield win
    bus.reset()
    win.close()


def _show(bus, window, text="提示", **kwargs):
    return bus.show(ToastAnchor.MAIN, ToastRequest(text=text, scope=kwargs.pop("scope", "base"), **kwargs))


def test_stack_limit_and_newest_first(bus, window):
    for index in range(4):
        _show(bus, window, f"条目 {index}")
    order = bus._order[id(window)]
    assert len(order) == 4
    assert bus._records[order[0]].request.text == "条目 3"


def test_overflow_drops_oldest_but_keeps_error(bus, window):
    seen: list[ToastDismiss] = []
    bus.observe(lambda topic, payload: None)

    first = _show(bus, window, "旧提示")
    for index in range(3):
        _show(bus, window, f"填充 {index}")
    error = _show(bus, window, "关键错误", level="error")
    # 栈仍为 4，且错误条一定在
    assert len(bus._order[id(window)]) == 4
    assert error.toast_id in bus._records
    # 最旧的非 error 条被挤出
    assert first.toast_id not in bus._records
    assert seen == []


def test_stack_full_when_all_errors(bus, window):
    for index in range(4):
        _show(bus, window, f"错误 {index}", level="error")
    extra = _show(bus, window, "再来一条", level="error")
    assert extra.ok is False
    assert extra.code == str(ToastCode.STACK_FULL)


def test_dedupe_suppress(bus, window):
    first = _show(bus, window, "已保存", level="success", dedupe_key="save", dedupe=DedupePolicy.SUPPRESS)
    second = _show(bus, window, "已保存", level="success", dedupe_key="save", dedupe=DedupePolicy.SUPPRESS)
    assert second.ok is True
    assert second.code == str(ToastCode.DUPLICATE_SUPPRESSED)
    assert second.toast_id == first.toast_id
    assert second.duplicate_of == first.toast_id
    assert len(bus._records) == 1


def test_dedupe_restart_increments_repeat(bus, window):
    first = _show(bus, window, "正在刷新", level="info", dedupe_key="refresh", dedupe=DedupePolicy.RESTART)
    second = _show(bus, window, "正在刷新", level="info", dedupe_key="refresh", dedupe=DedupePolicy.RESTART)
    assert second.toast_id == first.toast_id
    assert bus._records[first.toast_id].repeat == 2


def test_dedupe_count_composes_text(bus, window):
    handle = _show(bus, window, "已清理 {count} 项", level="success", dedupe_key="clean", dedupe=DedupePolicy.COUNT)
    _show(bus, window, "已清理 {count} 项", level="success", dedupe_key="clean", dedupe=DedupePolicy.COUNT)
    record = bus._records[handle.toast_id]
    assert record.repeat == 2
    assert record.toast._text_label.text() == "已清理 2 项"


def test_replace_channel_keeps_single(bus, window):
    first = _show(bus, window, "正在缓冲…", channel="player", mode=ToastMode.REPLACE)
    second = _show(bus, window, "正在连接…", channel="player", mode=ToastMode.REPLACE)
    assert first.toast_id != second.toast_id
    assert first.toast_id not in bus._records
    assert second.toast_id in bus._records
    assert len([item for item in bus._records.values() if item.channel == "player"]) == 1


def test_coalesce_channel_merges(bus, window):
    first = _show(bus, window, "同步 10%", channel="sync", mode=ToastMode.COALESCE)
    second = _show(bus, window, "同步 20%", channel="sync", mode=ToastMode.COALESCE)
    assert second.toast_id == first.toast_id
    assert bus._records[first.toast_id].request.text == "同步 20%"
    assert bus._records[first.toast_id].repeat == 2


def test_update_recomputes_and_blocks_after_close(bus, window):
    handle = _show(bus, window, "加载中", level="loading", life=0)
    assert bus.state_of(handle.toast_id) is ToastState.SHOWN
    result = bus.update(handle.toast_id, {"text": "完成", "level": ToastLevel.SUCCESS, "persist": False})
    assert result.ok is True
    assert bus._records[handle.toast_id].request.text == "完成"
    assert bus._records[handle.toast_id].toast.is_persistent() is False
    bus.dismiss(handle.toast_id, ToastDismissReason.MANUAL, immediate=True)
    assert bus.state_of(handle.toast_id) is ToastState.CLOSED
    closed = bus.update(handle.toast_id, {"text": "再改"})
    assert closed.ok is False
    assert closed.code == str(ToastCode.UPDATING_CLOSED)


def test_dismiss_callback_and_reason(bus, window):
    events: list[ToastDismiss] = []
    handle = bus.show(
        ToastAnchor.MAIN,
        ToastRequest(text="可关闭", scope="base", on_dismiss=events.append),
    )
    bus.dismiss(handle.toast_id, ToastDismissReason.MANUAL, immediate=True)
    assert len(events) == 1
    assert events[0].reason is ToastDismissReason.MANUAL
    assert events[0].by_user is True
    assert events[0].toast_id == handle.toast_id


def test_anchor_is_window_not_page(bus, window):
    """锚点只能是顶层窗口：页面销毁后提示仍在（旧的按页面分组会丢）。"""
    from PySide6.QtWidgets import QWidget

    page = QWidget(window)
    handle = bus.show(ToastAnchor.AUTO, ToastRequest(text="切页后仍在", scope="base"))
    page.deleteLater()
    window.layout()  # 触发事件处理前的占位
    assert bus.state_of(handle.toast_id) is ToastState.SHOWN
    record = bus._records[handle.toast_id]
    assert record.anchor is window


def test_cross_thread_show_is_queued(bus, window):
    from PySide6.QtCore import QObject, Qt, QThread, Signal
    from PySide6.QtWidgets import QApplication

    class Worker(QObject):
        done = Signal()

        def run(self) -> None:
            for index in range(3):
                bus.show(ToastAnchor.MAIN, ToastRequest(text=f"线程 {index}", scope="base"))
            self.done.emit()

    thread = QThread()
    worker = Worker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    # 直接连接：``quit`` 必须在本线程内生效，否则主线程卡在 wait() 里等自己
    worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
    thread.start()
    assert thread.wait(3000)
    QApplication.processEvents()
    texts = sorted(record.request.text for record in bus._records.values())
    assert texts == ["线程 0", "线程 1", "线程 2"]
    worker.deleteLater()
    thread.deleteLater()


def test_rate_limit(bus, window):
    codes = []
    for index in range(21):
        codes.append(_show(bus, window, f"刷屏 {index}", scope="burst").code)
    assert str(ToastCode.RATE_LIMITED) in codes


def test_clear_by_scope_and_channel(bus, window):
    _show(bus, window, "a", scope="p1", channel="x")
    _show(bus, window, "b", scope="p1", channel="y")
    _show(bus, window, "c", scope="p2")
    assert bus.clear(scope="p1", channel="x") == 1
    assert bus.clear(scope="p1") == 1
    assert len(bus.active(scope="p2")) == 1


def test_persistent_watchdog_closes_leak(bus, window):
    handle = _show(bus, window, "永不收敛", level="loading", life=0)
    bus._on_leak(handle.toast_id)
    assert bus.state_of(handle.toast_id) is ToastState.CLOSED


def test_long_text_folds_and_expands(bus, window):
    """超过 3 行折叠；展开/收起必须改变高度（曾因 sizeHint 缓存而失效）。"""
    from PySide6.QtWidgets import QApplication

    handle = _show(bus, window, "长文本" * 40, level="info", life=8000)
    toast = bus._records[handle.toast_id].toast
    QApplication.processEvents()
    collapsed = toast.height()
    assert toast._more_label.isVisible() is True
    toast._toggle_expanded()
    QApplication.processEvents()
    expanded = toast.height()
    assert expanded > collapsed
    toast._toggle_expanded()
    QApplication.processEvents()
    assert toast.height() == collapsed


def test_invalid_inputs_degrade(bus, window):
    empty = _show(bus, window, "   ")
    assert empty.ok is False and empty.code == str(ToastCode.EMPTY_TEXT)
    invalid = _show(bus, window, "级别非法", level="nope")
    assert invalid.code == str(ToastCode.INVALID_LEVEL)
    assert bus._records[invalid.toast_id].level is ToastLevel.INFO
    clamped = _show(bus, window, "太长", life=999_999)
    assert clamped.code == str(ToastCode.LIFE_CLAMPED)
    bad_channel = _show(bus, window, "通道非法", channel="BAD CHANNEL")
    assert bad_channel.code == str(ToastCode.INVALID_CHANNEL)
