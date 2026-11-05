"""媒体与小号组件的契约：预览、翻页、切换、溢出、回顶、图标与确认气泡。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QSizePolicy, QWidget

from sllkgui.appcore import ColorPalette
from sllkgui.guicore import (
    CAvatarGroup,
    CCarousel,
    CConfirmPopup,
    CFluid,
    CGalleria,
    CIconField,
    CImage,
    CInputIcon,
    CScrollTop,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(800, 500)
    widget.show()
    QTest.qWait(30)
    yield widget
    widget.hide()
    widget.deleteLater()


def _pixmap(width: int = 80, height: int = 60) -> QPixmap:
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(ColorPalette.custom_context_color))
    return pixmap


def test_image_click_opens_preview_and_closes(host):
    image = CImage(_pixmap(), caption="Preview", parent=host)
    image.setGeometry(40, 40, 200, 140)
    image.show()
    seen = []
    image.clicked.connect(lambda: seen.append(True))

    QTest.mouseClick(image, Qt.LeftButton)
    assert seen == [True]
    assert image.is_preview_open()
    assert len(image.preview_widget().buttons()) == 3

    image.close_preview()
    assert not image.is_preview_open()


def test_carousel_moves_pages_and_loops(host):
    carousel = CCarousel(
        [{"title": f"Item {index}", "description": "demo", "image": _pixmap()} for index in range(4)],
        num_visible=1,
        num_scroll=1,
        loop=True,
        parent=host,
    )
    carousel.setGeometry(20, 20, 320, 220)
    carousel.show()
    QTest.qWait(60)
    assert carousel.page_count() == 4

    carousel.next()
    QTest.qWait(300)
    assert carousel.current_index() == 1

    carousel.prev()
    QTest.qWait(300)
    assert carousel.current_index() == 0

    carousel.prev()
    QTest.qWait(300)
    assert carousel.current_index() == 3


def test_galleria_switches_and_loops(host):
    galleria = CGalleria(
        [{"title": f"Photo {index}", "image": _pixmap()} for index in range(3)],
        loop=True,
        parent=host,
    )
    galleria.setGeometry(20, 20, 360, 300)
    galleria.show()
    QTest.qWait(40)
    seen = []
    galleria.itemChanged.connect(seen.append)

    galleria.set_index(2)
    assert galleria.current_index() == 2
    assert seen == [2]
    assert galleria.thumbnails()[2].is_active()

    galleria.next()
    assert galleria.current_index() == 0
    assert seen[-1] == 0


def test_avatar_group_counts_overflow(host):
    group = CAvatarGroup(["A", "B", "C", "D", "E", "F"], max_count=4, parent=host)
    assert group.total_count() == 6
    assert group.visible_avatar_count() == 3
    assert group.overflow_count() == 3
    assert len(group.avatars()) == 3

    small = CAvatarGroup(["A", "B"], max_count=4, parent=host)
    assert small.visible_avatar_count() == 2
    assert small.overflow_count() == 0


def test_scroll_top_scrolls_back(host):
    area = QScrollArea(host)
    area.setGeometry(20, 20, 240, 180)
    content = QWidget()
    content.setMinimumHeight(800)
    area.setWidget(content)
    area.setWidgetResizable(True)
    area.show()
    QTest.qWait(30)
    area.verticalScrollBar().setValue(200)

    button = CScrollTop(area)
    QTest.qWait(220)
    assert button.isVisible()
    QTest.mouseClick(button, Qt.LeftButton)
    QTest.qWait(420)
    assert area.verticalScrollBar().value() == 0


def test_icon_field_manages_both_sides(host):
    field = CIconField(placeholder="Search", left_icon="icon_search", parent=host)
    assert field.has_icon("left")
    assert not field.has_icon("right")
    assert field.field().actions() == []

    field.set_icon("icon_close", "right")
    assert field.has_icon("right")
    field.clear_icon("left")
    assert not field.has_icon("left")
    assert field.has_icon("right")
    field.clear_icon()
    assert not field.has_icon("left")
    assert not field.has_icon("right")

    assert CInputIcon is CIconField


def test_confirm_popup_accept_and_reject(host):
    anchor = QWidget(host)
    anchor.setGeometry(80, 60, 120, 32)
    anchor.show()

    popup = CConfirmPopup(parent=host)
    events = []
    popup.accepted.connect(lambda: events.append("accepted"))
    popup.rejected.connect(lambda: events.append("rejected"))

    popup.show_at(anchor, "Delete this item?")
    QTest.qWait(30)
    assert popup.isVisible()
    QTest.mouseClick(popup.accept_button(), Qt.LeftButton)
    QTest.qWait(30)
    assert events == ["accepted"]

    popup.show_at(anchor, "Keep it?")
    QTest.qWait(30)
    QTest.mouseClick(popup.reject_button(), Qt.LeftButton)
    QTest.qWait(30)
    assert events[-1] == "rejected"


def test_fluid_makes_content_expand(host):
    child = QWidget()
    fluid = CFluid(child, parent=host)
    fluid.resize(240, 120)
    assert fluid.content() is child
    assert child.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    replacement = QWidget()
    fluid.set_content(replacement)
    assert fluid.content() is replacement
