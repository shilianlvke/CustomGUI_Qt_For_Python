"""媒体、文件、图表与杂项预览页。"""

from pathlib import Path

from PySide6.QtCore import QMargins
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, Language, PathFactory
from customgui.guicore import (
    CAvatarGroup,
    CButton,
    CCard,
    CCarousel,
    CChart,
    CConfirmPopup,
    CFileUpload,
    CFluid,
    CGalleria,
    CIconField,
    CImage,
    CScrollArea,
    CScrollTop,
)

_LANG = "app.media_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _images() -> list[str]:
    paths = [PathFactory.set_jpg_image("头像"), PathFactory.set_jpg_image("托盘"), PathFactory.set_svg_image("mihoutao")]
    return [str(Path(path)) for path in paths if path and Path(path).is_file()]


def _card(title: str, content: QWidget) -> CCard:
    card = CCard()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(QMargins(12, 10, 12, 12))
    layout.setSpacing(8)
    label = QLabel(title)
    font = QFont(AppSettings.family, AppSettings.subtitle_size)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    layout.addWidget(label)
    layout.addWidget(content)
    return card


def _image_demo() -> QWidget:
    sources = _images()
    image = CImage(sources[0] if sources else None, caption=_t("image_caption"), preview=True)
    image.setMinimumSize(260, 220)
    return image


def _carousel_demo() -> QWidget:
    sources = _images()
    items = [
        {"title": f"{_t('carousel_item')} {index + 1}", "description": _t("carousel_desc"), "image": sources[index % len(sources)]}
        for index in range(6)
    ] if sources else []
    carousel = CCarousel(items, num_visible=3)
    carousel.setMinimumHeight(240)
    return carousel


def _galleria_demo() -> QWidget:
    sources = _images()
    items = [{"title": f"{_t('gallery_item')} {index + 1}", "image": sources[index % len(sources)]} for index in range(4)] if sources else []
    galleria = CGalleria(items)
    galleria.setMinimumHeight(360)
    return galleria


def _file_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    advanced = CFileUpload(mode="advanced", accept=".jpg,.png,.svg,.pdf", max_file_size=5 * 1024 * 1024)
    basic = CFileUpload(mode="basic", accept=".jpg,.png,.svg,.pdf", multiple=False)
    status = QLabel(_t("file_hint"))
    status.setStyleSheet("color: palette(mid);")
    advanced.filesSelected.connect(lambda files: status.setText(f"{len(files)} {_t('files')}"))
    basic.filesSelected.connect(lambda files: status.setText(f"{len(files)} {_t('files')}"))
    layout.addWidget(advanced)
    layout.addWidget(basic)
    layout.addWidget(status)
    return box


def _chart_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    line = CChart("line", _t("chart_title"))
    line.set_data([{"name": _t("series"), "values": [12, 19, 14, 23, 18, 27], "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]}])
    line.setMinimumHeight(220)
    bar = CChart("bar", _t("chart_bar"))
    bar.set_data([{"name": _t("series"), "values": [7, 12, 9, 15], "labels": ["Q1", "Q2", "Q3", "Q4"]}])
    bar.setMinimumHeight(220)
    pie = CChart("pie", _t("chart_pie"))
    pie.set_data([{"name": _t("series"), "values": [40, 30, 20, 10], "labels": ["A", "B", "C", "D"]}])
    pie.setMinimumHeight(220)
    layout.addWidget(line)
    layout.addWidget(bar)
    layout.addWidget(pie)
    return box


def _misc_demo() -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    avatars = CAvatarGroup(["A", "B", "C", "D", "E"], max_count=4)
    icon_field = CIconField(placeholder=_t("search_hint"), left_icon="icon_search", right_icon="icon_close")
    fluid = CFluid(icon_field)

    popup = CConfirmPopup(_t("confirm_message"), _t("yes"), _t("no"))
    trigger = CButton(_t("confirm_open"), variant="outlined", severity="warning")
    trigger.clicked.connect(lambda: popup.show_at(trigger))
    result = QLabel("")

    def accepted():
        result.setText(_t("accepted"))

    def rejected():
        result.setText(_t("rejected"))

    popup.accepted.connect(accepted)
    popup.rejected.connect(rejected)

    layout.addWidget(avatars)
    layout.addWidget(fluid, 1)
    layout.addWidget(trigger)
    layout.addWidget(result)
    return box


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("mediaPreviewPage")
    window.ui.load_pages.pages.addWidget(page)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(QMargins(0, 0, 0, 0))
    outer.setSpacing(0)

    scroller = CScrollArea()
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(QMargins(6, 6, 6, 6))
    layout.setSpacing(6)
    scroller.setWidget(content)
    scroller.setWidgetResizable(True)
    outer.addWidget(scroller)

    scroll_top = CScrollTop(scroller)
    scroll_top.raise_()

    for title, widget in (
        (_t("group_image"), _image_demo()),
        (_t("group_carousel"), _carousel_demo()),
        (_t("group_galleria"), _galleria_demo()),
        (_t("group_file"), _file_demo()),
        (_t("group_chart"), _chart_demo()),
        (_t("group_misc"), _misc_demo()),
    ):
        layout.addWidget(_card(title, widget))
    layout.addStretch()
    return page


class MediaPreviewPage:
    """PAGE 协议入口。"""

    def load_page(self):
        _build_page(self)


PAGE = MediaPreviewPage
