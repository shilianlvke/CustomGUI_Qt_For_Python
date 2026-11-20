"""pytest-qt 交互断言：通知条的 closed 信号与自动消失（RV-11）。

依赖 pyproject.toml 声明的 pytest-qt；用 qtbot.waitSignal 等待真实信号，
而不是靠 QTest.qWait 固定睡眠或检查内部栈。
"""

from __future__ import annotations

import pytest

from sllkgui.guicore import CToast


@pytest.fixture
def host(qapp):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    widget.resize(640, 480)
    yield widget
    CToast.clear(widget)
    widget.close()


def test_toast_emits_closed_when_life_expires(qtbot, host):
    toast = CToast.show_message(host, "interaction", "Info", "info", life=60)
    with qtbot.waitSignal(toast.closed, timeout=3000):
        pass
    assert toast not in CToast._stacks.get(id(host), [])


def test_dismiss_emits_closed(qtbot, host):
    toast = CToast.show_message(host, "dismiss me", "Info", "info", life=0)
    with qtbot.waitSignal(toast.closed, timeout=3000):
        toast.dismiss(immediate=True)
