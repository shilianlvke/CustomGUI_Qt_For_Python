"""浮层组件契约：对话框、抽屉、确认框、浮层面板的开合与几何。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from customgui.guicore import CConfirmDialog, CDialog, CDrawer, COverlayPanel


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


# ----------------------------------------------------------------------
# 抽屉：与左列「软件信息」抽屉同构，并限制在内容区内
# ----------------------------------------------------------------------
class _FakeMain(QWidget):
    """带内容区的最小主窗口替身（只提供 ui.content_area_frame）。"""

    def __init__(self):
        from types import SimpleNamespace

        super().__init__()
        self.resize(900, 600)
        self.content_area_frame = QWidget(self)
        self.content_area_frame.setGeometry(60, 50, 780, 500)
        self.ui = SimpleNamespace(content_area_frame=self.content_area_frame)


def test_drawer_is_confined_to_content_area(qapp):
    """抽屉只覆盖内容区，不压住左侧菜单、标题栏与版权栏。"""
    parent = _FakeMain()
    parent.show()
    QTest.qWait(60)

    drawer = CDrawer("Software Info", position="left", size=240, parent=parent)
    drawer.open_dialog()
    QTest.qWait(320)

    anchor = parent.content_area_frame
    origin = anchor.mapToGlobal(QPoint(0, 0))
    assert drawer.geometry() == QRect(origin, anchor.size())
    assert drawer.bounds() == QRect(origin, anchor.size())
    # 非模态：打开抽屉时标题栏/菜单仍可操作（与左列抽屉一致）
    assert drawer.isModal() is False

    drawer.reject()
    QTest.qWait(320)


def test_drawer_follows_parent_resize(qapp):
    """父窗口缩放（最大化/还原）后抽屉重新贴边，不会停在旧位置。"""
    parent = _FakeMain()
    parent.show()
    QTest.qWait(60)

    drawer = CDrawer("Details", position="right", size=240, parent=parent)
    drawer.open_dialog()
    QTest.qWait(320)
    assert drawer.card().x() + drawer.card().width() == drawer.width()

    parent.resize(1100, 760)
    parent.content_area_frame.setGeometry(60, 50, 980, 660)
    QTest.qWait(120)

    anchor = parent.content_area_frame
    assert drawer.geometry() == QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
    card = drawer.card().geometry()
    assert card.x() + card.width() == drawer.width()
    assert card.height() == drawer.height()

    drawer.reject()
    QTest.qWait(320)


def test_drawer_header_matches_left_column(host):
    """头部复用左列抽屉的结构与样式表对象名（47px + 胶囊 + 30px 控件位）。"""
    drawer = CDrawer("Software Info", icon="icon_setting", parent=host)
    assert drawer.header is not None
    assert drawer.header.height() == 47
    assert drawer.title_label is not None
    assert drawer.title_label.text() == "Software Info"
    assert drawer.title_label.objectName() == "CLeftColumnTitle_Label"
    assert drawer._scroll.widget() is not None  # 内容放在滚动区里，超高可滚动

    drawer.set_title("")
    assert drawer.title_label.text() == ""


def test_drawer_all_positions_flush_to_anchor(host):
    """四个方向的卡片都贴住锚点对应的边。"""
    drawers = {}
    for position, size in (("left", 220), ("right", 220), ("top", 180), ("bottom", 180)):
        drawer = CDrawer("Details", position=position, size=size, parent=host)
        drawer.open_dialog()
        QTest.qWait(300)
        drawers[position] = drawer

    left = drawers["left"].card().geometry()
    assert left.left() == 0 and left.height() == drawers["left"].height()

    right = drawers["right"].card().geometry()
    assert right.right() == drawers["right"].width() - 1

    top = drawers["top"].card().geometry()
    assert top.top() == 0 and top.width() == drawers["top"].width()

    bottom = drawers["bottom"].card().geometry()
    assert bottom.bottom() == drawers["bottom"].height() - 1

    for drawer in drawers.values():
        drawer.reject()
    QTest.qWait(320)


def test_drawer_title_and_icon_can_change(host):
    drawer = CDrawer("Filters", icon="icon_search", parent=host)
    drawer.set_title("Details")
    drawer.set_icon("icon_report")
    assert drawer.title_label.text() == "Details"
    assert drawer._icon_name == "icon_report"
