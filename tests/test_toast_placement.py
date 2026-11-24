"""Toast 落位回归：边距、标题栏避让、堆叠与动画重排只有一套实现。

守护的是三条真实缺陷（同一条提示经不同触发路径落在不同位置）：

1. 总线直接读 ``title_bar.height()``，窗口尚未布局时该值是构造尺寸（实测 480），
   启动期弹出的提示被推到页面中间；
2. ``CToast.show_message`` 从 margin 起算、忽略标题栏，卡片压在标题栏里；
   边距又只作用到控件外框，而外框含一圈透明阴影，卡片离窗口边多出几个像素；
3. 滑入动画的终点是旧位置，重排后仍在跑，几十毫秒后把新坐标覆盖回去，
   表现为两条提示完全重叠。
"""

from __future__ import annotations

import pytest

from sllkgui.appcore.feedback import ToastAnchor, ToastLevel, ToastRequest
from sllkgui.guicore.feedback import reset_toast_bus


@pytest.fixture
def bus(qapp):
    bus = reset_toast_bus()
    yield bus
    bus.reset()


@pytest.fixture
def host(qapp, bus, monkeypatch):
    """带自定义标题栏的宿主：模拟主窗口的 ``ui.title_bar`` 结构。"""
    from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

    win = QWidget()
    win.resize(1200, 800)
    #: 标题栏容器固定 40px，内部标题栏由布局拉伸（与 UiMainWindow 同构）
    frame = QFrame(win)
    frame.setFixedHeight(40)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    bar = QWidget(frame)
    layout.addWidget(bar)
    ui = QWidget(win)
    ui.title_bar = bar
    win.ui = ui
    win.show()
    bus.set_sources(main=lambda: win, settings=lambda: None)
    yield win
    bus.reset()
    win.close()


def _card(toast, window):
    """卡片可见矩形 ``(left, top, right, bottom)``：去掉控件内的透明阴影。"""
    from PySide6.QtCore import QPoint

    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    metrics = toast_metrics()
    point = toast.mapTo(window, QPoint(0, 0))
    left = point.x() + metrics.inset_x
    top = point.y() + metrics.inset_y
    return (
        left,
        top,
        left + toast.width() - 2 * metrics.inset_x,
        top + toast.height() - metrics.inset_y - metrics.inset_bottom,
    )


def _show(bus, text, *, scope="base", life=8000, **kwargs):
    return bus.show(ToastAnchor.MAIN, ToastRequest(text=text, scope=scope, life=life, **kwargs))


def _settle(qapp, ms: int = 320) -> None:
    """等入场动画走完：滑入未结束前的坐标是动画中间值，不能用来断言落位。"""
    from PySide6.QtTest import QTest

    QTest.qWait(ms)
    qapp.processEvents()


# ----------------------------------------------------------------------
# 单条落位
# ----------------------------------------------------------------------
def test_card_right_gap_equals_configured_margin(bus, host, qapp):
    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    metrics = toast_metrics()
    handle = _show(bus, "已保存", level=ToastLevel.SUCCESS)
    _settle(qapp)
    toast = bus._records[handle.toast_id].toast
    *_, right, _ = _card(toast, host)
    assert abs((host.width() - right) - metrics.margin) <= 1


def test_toast_sits_below_title_bar(qapp, bus, host):
    """第一条提示必须让开标题栏，且间距等于 TITLE_BAR_GAP + margin。"""
    from sllkgui.guicore.custom_ui.feedback.placement import TITLE_BAR_GAP, toast_metrics

    metrics = toast_metrics()
    handle = _show(bus, "已保存", level=ToastLevel.SUCCESS)
    _settle(qapp)
    toast = bus._records[handle.toast_id].toast
    _, top, _, _ = _card(toast, host)
    expected = 40 + TITLE_BAR_GAP + metrics.margin
    assert abs(top - expected) <= 2, f"卡片顶边 {top}，期望 {expected}"


def test_offset_survives_unlaid_out_window(qapp, bus):
    """布局尚未发生时，标题栏高度不能取控件的构造尺寸（曾把提示推到页面中间）。"""
    from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

    from sllkgui.guicore.custom_ui.feedback.placement import TITLE_BAR_GAP

    win = QWidget()
    win.resize(1200, 800)
    frame = QFrame(win)
    frame.setFixedHeight(40)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    bar = QWidget(frame)
    layout.addWidget(bar)
    # 未 show = 未布局：主窗口里这个控件实测是 640x480 的构造尺寸，不可信
    bar.resize(640, 480)
    ui = QWidget(win)
    ui.title_bar = bar
    win.ui = ui
    try:
        assert bar.height() > 40, "前提失效：未布局的标题栏高度应当失真"
        bus.set_sources(main=lambda: win, settings=lambda: None)
        handle = _show(bus, "启动期提示", level=ToastLevel.WARN)
        toast = bus._records[handle.toast_id].toast
        assert toast._offset_top == 40 + TITLE_BAR_GAP
    finally:
        bus.reset()
        win.close()
        win.deleteLater()


def test_host_without_title_bar_uses_margin_only(qapp, bus):
    """普通宿主没有自定义标题栏，不得凭空避让。（曾用固定 56px 兜底）"""
    from PySide6.QtWidgets import QWidget

    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    metrics = toast_metrics()
    plain = QWidget()
    plain.resize(900, 600)
    plain.show()
    bus.set_sources(main=lambda: plain, settings=lambda: None)
    try:
        handle = _show(bus, "普通宿主")
        toast = bus._records[handle.toast_id].toast
        assert toast._offset_top == 0
        _, top, _, _ = _card(toast, plain)
        assert abs(top - metrics.margin) <= 1
    finally:
        bus.reset()
        plain.close()
        plain.deleteLater()


# ----------------------------------------------------------------------
# 堆叠与重排
# ----------------------------------------------------------------------
def test_stack_spacing_and_order(qapp, bus, host):
    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    metrics = toast_metrics()
    for index in range(3):
        _show(bus, f"条目 {index}", scope=f"s{index}")
    _settle(qapp, 420)
    # 按栈顺序取（最新在前），不能按显示顺序取
    order = bus._order[id(host)]
    rects = [_card(bus._records[tid].toast, host) for tid in order]
    assert len(rects) == 3
    # 最新的在最上面
    assert rects[0][1] < rects[1][1] < rects[2][1], f"栈里最旧的反倒更靠上: {[r[1] for r in rects]}"
    gaps = [rects[index + 1][1] - rects[index][3] for index in range(2)]
    assert all(abs(gap - metrics.spacing) <= 1 for gap in gaps), gaps
    assert all(gap >= 0 for gap in gaps), f"堆叠重叠: {gaps}"


def test_reflow_stops_running_slide(bus, host):
    """重排必须停掉滑入动画，否则旧终点会把新坐标覆盖回去（两条完全重叠）。"""
    from PySide6.QtWidgets import QApplication

    first = _show(bus, "甲", scope="a")
    QApplication.processEvents()
    toast = bus._records[first.toast_id].toast
    toast._stop_slide()  # 模拟动画进行中
    toast._slide.start()
    assert toast._slide.state() == toast._slide.State.Running

    _show(bus, "乙", scope="b")
    QApplication.processEvents()
    assert toast._slide.state() != toast._slide.State.Running, "重排后旧动画仍在跑"
    second = bus._order[id(host)][0]
    rects = [_card(bus._records[tid].toast, host) for tid in (second, first.toast_id)]
    assert rects[0][1] != rects[1][1], "两条提示落在同一位置"


def test_resize_keeps_toasts_inside(qapp, bus, host):
    from PySide6.QtCore import QPoint

    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    metrics = toast_metrics()
    handles = [_show(bus, f"条目 {index}", scope=f"r{index}") for index in range(2)]
    _settle(qapp, 360)
    host.resize(760, 620)
    _settle(qapp, 240)
    for handle in handles:
        toast = bus._records[handle.toast_id].toast
        point = toast.mapTo(host, QPoint(0, 0))
        assert point.x() >= 0 and point.y() >= 0
        assert point.x() + toast.width() <= host.width() + 1
        *_, right, _ = _card(toast, host)
        assert abs((host.width() - right) - metrics.margin) <= 1


# ----------------------------------------------------------------------
# 两套入口必须同源
# ----------------------------------------------------------------------
def test_legacy_show_message_matches_bus(bus, host):
    """``CToast.show_message`` 与 ``toast_bus()`` 必须落在同一位置。"""
    from sllkgui.guicore import CToast

    handle = _show(bus, "总线", scope="bus")
    bus_toast = bus._records[handle.toast_id].toast
    bus_card = _card(bus_toast, host)
    bus.dismiss(handle.toast_id, immediate=True)

    direct = CToast.show_message(host, "组件", "组件", "info", life=8000)
    try:
        direct_card = _card(direct, host)
        assert abs(direct_card[0] - bus_card[0]) <= 1, (direct_card, bus_card)
        assert abs(direct_card[1] - bus_card[1]) <= 1, (direct_card, bus_card)
    finally:
        CToast.clear(host)


def test_metrics_come_from_single_place():
    """组件与总线都必须走 ``placement.toast_metrics``，不得各自读配置。"""
    from pathlib import Path

    import sllkgui.guicore.custom_ui.feedback.toast as toast_module
    from sllkgui.guicore.custom_ui.feedback.placement import toast_metrics

    source = Path(toast_module.__file__).read_text(encoding="utf-8")
    assert "toast_margin" not in source, "渲染器不应自己读 toast_margin"
    assert "toast_spacing" not in source, "渲染器不应自己读 toast_spacing"
    metrics = toast_metrics()
    assert metrics.margin >= 0 and metrics.spacing >= 0 and metrics.shadow >= 0


def test_placement_is_qt_dependency_free_for_bad_config(monkeypatch):
    """配置读取失败时回落默认值，不抛给调用方。"""
    from sllkgui.guicore.custom_ui.feedback import placement

    monkeypatch.setattr(placement, "_DEFAULTS", placement.ToastMetrics(margin=20, spacing=8, shadow=5))

    class _Boom:
        @property
        def feedback(self):
            raise RuntimeError("config broken")

    monkeypatch.setitem(__import__("sys").modules, "sllkgui.appcore", _Boom())
    metrics = placement.toast_metrics()
    assert metrics.margin == 20 and metrics.spacing == 8 and metrics.shadow == 5
