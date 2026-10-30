"""反馈与状态原子件契约：消息、通知、标签、徽标、标签片、头像、骨架、进度、分割线。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from GuiCore import (
    CAvatar,
    CBadge,
    CChip,
    CDivider,
    CMessage,
    CProgressBar,
    CSkeleton,
    CTag,
    CToast,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(420, 300)
    widget.show()
    yield widget
    CToast.clear(widget)
    widget.hide()
    widget.deleteLater()


# ----------------------------------------------------------------------
# 消息
# ----------------------------------------------------------------------
def test_message_normalizes_error_alias(host):
    message = CMessage("oops", title="Error", severity="error", parent=host)
    assert message.severity() == "danger"
    message.set_severity("success")
    assert message.severity() == "success"


def test_message_close_hides_and_emits(host):
    message = CMessage("closable", title="Info", severity="info", closable=True, parent=host)
    seen = []
    message.closed.connect(lambda: seen.append(True))
    message.show()
    message._close_button.click()
    assert seen == [True]
    assert message.isHidden()


def test_message_outlined_and_titles(host):
    message = CMessage("body", title="Title", severity="warn", outlined=True, parent=host)
    assert message.title() == "Title"
    assert message.text() == "body"
    message.set_title("Changed")
    assert message._title_label.text() == "Changed"


# ----------------------------------------------------------------------
# 标签 / 徽标 / 标签片 / 头像
# ----------------------------------------------------------------------
def test_tag_width_follows_text(host):
    short = CTag("A", parent=host)
    long = CTag("A much longer tag", parent=host)
    assert long.sizeHint().width() > short.sizeHint().width()
    assert short.height() == 24


def test_tag_severity_and_rounded(host):
    tag = CTag("Primary", "primary", rounded=True, parent=host)
    assert tag.severity() == "primary"
    tag.set_severity("danger")
    assert tag.severity() == "danger"
    tag.set_rounded(False)


def test_badge_dot_is_square(host):
    badge = CBadge("", "success", dot=True, parent=host)
    assert badge.width() == badge.height()


def test_badge_attach_tracks_target(host):
    target = QWidget(host)
    target.setGeometry(50, 50, 40, 40)
    target.show()
    badge = CBadge.attach(target, "3", "danger", "sm")
    QTest.qWait(20)
    assert badge.parent() is host
    assert badge.x() > target.x() + target.width() - badge.width()
    assert badge.y() < target.y()


def test_chip_remove_click_emits(host):
    chip = CChip("Removable", removable=True, parent=host)
    chip.show()
    chip.grab()
    seen = []
    chip.removed.connect(lambda: seen.append(True))
    QTest.mouseClick(chip, Qt.LeftButton, pos=chip._remove_rect.center().toPoint())
    assert seen == [True]


def test_avatar_sizes(host):
    avatar = CAvatar("SL", size="xl", parent=host)
    assert avatar.width() == 64 and avatar.height() == 64
    avatar.set_size(48)
    assert avatar.width() == 48
    square = CAvatar("AB", shape="square", parent=host)
    assert square.width() == 40


# ----------------------------------------------------------------------
# 骨架 / 进度 / 分割线
# ----------------------------------------------------------------------
def test_skeleton_shapes(host):
    circle = CSkeleton(40, 40, shape="circle", parent=host)
    assert circle.width() == circle.height() == 40
    text = CSkeleton(120, 12, shape="text", parent=host)
    assert text.width() == 120
    text.set_animation(False)
    assert not text.is_animating()


def test_progress_bar_clamps_and_emits(host):
    bar = CProgressBar(10, maximum=100, parent=host)
    seen = []
    bar.valueChanged.connect(seen.append)
    bar.setValue(150)
    assert bar.value() == 100
    assert seen[-1] == 100
    bar.setValue(-10)
    assert bar.value() == 0


def test_divider_orientation(host):
    horizontal = CDivider(parent=host)
    vertical = CDivider(orientation="vertical", parent=host)
    assert horizontal.height() == 20
    assert vertical.width() == 21


# ----------------------------------------------------------------------
# 通知
# ----------------------------------------------------------------------
def test_toast_stacks_and_auto_dismiss(host):
    CToast.show_message(host, "saved", "Success", "success", life=80)
    CToast.show_message(host, "check this", "Info", "info", life=80)
    stack = CToast._stacks.get(id(host), [])
    assert len(stack) == 2
    assert stack[0].y() < stack[1].y()  # 最新的在最上面
    QTest.qWait(500)
    assert CToast._stacks.get(id(host), []) == []


def test_toast_respects_max_stack(host):
    for index in range(6):
        CToast.show_message(host, f"toast {index}", "Info", "info", life=5000)
    assert len(CToast._stacks.get(id(host), [])) <= 4


def test_toast_clear(host):
    CToast.show_message(host, "a", "Info", "info", life=5000)
    CToast.show_message(host, "b", "Info", "info", life=5000)
    CToast.clear(host)
    QTest.qWait(50)
    assert CToast._stacks.get(id(host), []) == []


def test_message_simple_variant(host):
    message = CMessage("simple", title="Simple", severity="success", simple=True, parent=host)
    assert message._simple
    message.set_severity("info")
    assert message.severity() == "info"


def test_progress_vertical_orientation(host):
    bar = CProgressBar(50, orientation="vertical", height=10, parent=host)
    assert bar._vertical
    assert bar.width() == 10
    bar.setValue(100)
    assert bar.value() == 100
