"""浮层组件契约：对话框、抽屉、确认框、浮层面板的开合与几何。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from GuiCore import CConfirmDialog, CDialog, CDrawer, COverlayPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(800, 500)
    widget.show()
    yield widget
    widget.hide()
    widget.deleteLater()


def test_dialog_opens_centered(host):
    dialog = CDialog("Title", "Body text", width=400, parent=host)
    dialog.open_dialog()
    QTest.qWait(250)
    assert dialog.isVisible()
    card = dialog.card().geometry()
    assert card.width() == 400
    assert abs(card.center().x() - dialog.width() // 2) <= 2
    dialog.reject()
    QTest.qWait(250)
    assert not dialog.isVisible()


def test_dialog_emits_accepted_and_closes(host):
    dialog = CDialog("Title", "Body", accept_text="OK", reject_text="Cancel", parent=host)
    seen = []
    dialog.accepted.connect(lambda: seen.append(True))
    dialog.open_dialog()
    QTest.qWait(220)
    dialog.accept()
    QTest.qWait(250)
    assert seen == [True]
    assert not dialog.isVisible()


def test_dialog_escape_rejects(host):
    dialog = CDialog("Title", "Body", parent=host)
    seen = []
    dialog.rejected.connect(lambda: seen.append(True))
    dialog.open_dialog()
    QTest.qWait(220)
    QTest.keyClick(dialog, Qt.Key_Escape)
    QTest.qWait(250)
    assert seen == [True]
    assert not dialog.isVisible()


def test_dialog_without_header_still_opens(host):
    dialog = CDialog("", "Only body", closable=False, parent=host)
    dialog.open_dialog()
    QTest.qWait(220)
    assert dialog.isVisible()
    assert dialog.header is None
    dialog.reject()
    QTest.qWait(250)


def test_drawer_right_and_bottom_geometry(host):
    right = CDrawer("Notifications", position="right", size=300, parent=host)
    right.open_dialog()
    QTest.qWait(300)
    card = right.card().geometry()
    assert card.x() + card.width() == right.width()
    assert card.height() == right.height()
    right.reject()
    QTest.qWait(300)

    bottom = CDrawer("Details", position="bottom", size=240, parent=host)
    bottom.open_dialog()
    QTest.qWait(320)
    card = bottom.card().geometry()
    assert card.y() + card.height() == bottom.height()
    assert card.width() == bottom.width()
    bottom.reject()
    QTest.qWait(300)


def test_confirm_dialog_reports_choice(host):
    dialog = CConfirmDialog("Delete", "Are you sure?", "error", parent=host)
    seen = []
    dialog.accepted.connect(lambda: seen.append("accepted"))
    dialog.rejected.connect(lambda: seen.append("rejected"))
    dialog.open_dialog()
    QTest.qWait(220)
    assert dialog.isVisible()
    dialog.accept()
    QTest.qWait(250)
    assert seen == ["accepted"]


def test_overlay_panel_opens_below_target(host):
    target = QWidget(host)
    target.setGeometry(60, 60, 120, 32)
    target.show()
    QTest.qWait(30)

    panel = COverlayPanel(target, width=240)
    panel.set_content(QLabel("Panel content"))
    panel.open_panel()
    QTest.qWait(80)
    assert panel.is_open()
    assert panel.y() >= target.mapToGlobal(QPoint(0, target.height())).y()

    panel.close_panel()
    QTest.qWait(60)
    assert not panel.is_open()
