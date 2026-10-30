"""栏目切换过场的时序与清理约束。

约定：旧页擦除 → 原按钮 1→0 → 新按钮 0→1 → 新页展开，四段串联；
切换本身立即生效（不等动画），过场结束必须撤干净遮罩与临时状态。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEasingCurve, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from GuiCore import CPageTransition
from Guis.windows.main_window.functions import MainFunctions

LAYER_NAME = "CPageTransition_Layer"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def stack(qapp):
    widget = QStackedWidget()
    widget.resize(240, 160)
    for name, color in (("pageA", "#101010"), ("pageB", "#eeeeee")):
        page = QWidget()
        page.setObjectName(name)
        page.setStyleSheet(f"background: {color};")
        widget.addWidget(page)
    widget.setCurrentWidget(widget.widget(0))
    yield widget
    CPageTransition.cancel(widget)
    widget.close()
    widget.deleteLater()
    _flush_deletes()


@pytest.fixture
def fast_timing(monkeypatch):
    """把时间线压到 4×60ms，避免测试等 500ms 以上。"""
    curve = QEasingCurve(QEasingCurve.Type.Linear)
    monkeypatch.setattr(CPageTransition, "_timing", classmethod(lambda cls: (60, 60, 60, 60, curve)))
    return 240


class _FakeLayer:
    def __init__(self):
        self.out = 0.0
        self.inn = 0.0
        self.old = None
        self.new = None

    def set_out_progress(self, value):
        self.out = value

    def set_in_progress(self, value):
        self.inn = value


class _FakeButton:
    def __init__(self):
        self.progress = None

    def set_selection_progress(self, value):
        self.progress = value


def _layer(stack):
    return stack.findChild(QWidget, LAYER_NAME)


def _flush_deletes():
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _timeline_state():
    curve = QEasingCurve(QEasingCurve.Type.Linear)
    layer = _FakeLayer()
    old_button = _FakeButton()
    new_button = _FakeButton()
    state = SimpleNamespace(
        layer=layer,
        old_button=old_button,
        new_button=new_button,
        timing=(100, 100, 100, 100, curve),
        total=400,
    )
    return state


def test_timeline_runs_erase_buttons_reveal_in_order():
    state = _timeline_state()

    # 阶段 1：只擦除旧页，按钮都还没动
    CPageTransition._apply_frame(state, 0.1)
    assert state.layer.out == pytest.approx(0.4)
    assert state.old_button.progress is None
    assert state.new_button.progress is None

    # 阶段 2：旧页擦完，原按钮 1 -> 0
    CPageTransition._apply_frame(state, 0.35)
    assert state.layer.out == pytest.approx(1.0)
    assert state.old_button.progress == pytest.approx(0.6)
    assert state.new_button.progress is None

    # 阶段 3：原按钮落到 0，目标按钮 0 -> 1，页面尚未展开
    CPageTransition._apply_frame(state, 0.65)
    assert state.old_button.progress == pytest.approx(0.0)
    assert state.new_button.progress == pytest.approx(0.6)
    assert state.layer.inn == pytest.approx(0.0)

    # 阶段 4：目标按钮到 1，新页从左向右展开
    CPageTransition._apply_frame(state, 0.9)
    assert state.new_button.progress == pytest.approx(1.0)
    assert state.layer.inn == pytest.approx(0.6)


def test_switch_without_visible_stack_switches_instantly(stack):
    target = stack.widget(1)

    assert CPageTransition.switch(stack, target) is False
    assert stack.currentWidget() is target
    assert _layer(stack) is None


def test_switch_plays_wipe_then_cleans_up(stack, fast_timing):
    stack.show()
    QTest.qWait(30)
    target = stack.widget(1)

    assert CPageTransition.switch(stack, target) is True
    # 业务状态立即切换，遮罩位于最上层负责画面
    assert stack.currentWidget() is target
    layer = _layer(stack)
    assert layer is not None and layer.isVisible()
    assert stack.children()[-1] is layer

    QTest.qWait(fast_timing + 300)
    _flush_deletes()
    assert _layer(stack) is None
    stack.hide()


def test_new_switch_replaces_previous_layer(stack, fast_timing):
    stack.show()
    QTest.qWait(30)
    first, second = stack.widget(0), stack.widget(1)

    CPageTransition.switch(stack, second)
    QTest.qWait(40)
    CPageTransition.switch(stack, first)
    _flush_deletes()

    layers = [item for item in stack.findChildren(QWidget, LAYER_NAME) if item.isVisible()]
    assert len(layers) == 1
    assert stack.currentWidget() is first
    stack.hide()


def test_switch_to_current_page_is_noop(stack):
    stack.show()
    QTest.qWait(30)

    assert CPageTransition.switch(stack, stack.currentWidget()) is False
    assert _layer(stack) is None
    stack.hide()


def test_zero_timing_disables_animation(stack, monkeypatch):
    curve = QEasingCurve(QEasingCurve.Type.Linear)
    monkeypatch.setattr(CPageTransition, "_timing", classmethod(lambda cls: (0, 0, 0, 0, curve)))
    stack.show()
    QTest.qWait(30)
    target = stack.widget(1)

    assert CPageTransition.switch(stack, target) is False
    assert stack.currentWidget() is target
    assert _layer(stack) is None
    stack.hide()


def test_set_page_honours_animate_flag(stack, fast_timing):
    stack.show()
    QTest.qWait(30)
    window = SimpleNamespace(ui=SimpleNamespace(load_pages=SimpleNamespace(pages=stack)))
    target = stack.widget(1)

    MainFunctions.set_page(window, target, animate=False)
    assert stack.currentWidget() is target
    assert _layer(stack) is None

    MainFunctions.set_page(window, stack.widget(0))
    assert stack.currentWidget() is stack.widget(0)
    assert _layer(stack) is not None
    QTest.qWait(fast_timing + 300)
    stack.hide()
