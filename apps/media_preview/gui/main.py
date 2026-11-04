"""媒体、文件、图表与杂项预览页。"""

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import PathFactory
from customgui.guicore import (
    CAvatarGroup,
    CButton,
    CCarousel,
    CChart,
    CConfirmPopup,
    CFileUpload,
    CFluid,
    CGalleria,
    CIconField,
    CImage,
    CPreviewPage,
)


class MediaPreviewPage(CPreviewPage):
    """PAGE 协议入口：媒体展示与杂项组件。"""

    slug = "media_preview"
    scroll_top = True

    @staticmethod
    def _images() -> list[str]:
        paths = [PathFactory.set_jpg_image("头像"), PathFactory.set_jpg_image("托盘"), PathFactory.set_svg_image("mihoutao")]
        return [str(Path(path)) for path in paths if path and Path(path).is_file()]

    @classmethod
    def _image_demo(cls) -> QWidget:
        sources = cls._images()
        image = CImage(sources[0] if sources else None, caption=cls.tr("image_caption"), preview=True)
        image.setMinimumSize(260, 220)
        return image

    @classmethod
    def _carousel_demo(cls) -> QWidget:
        sources = cls._images()
        items = [
            {"title": f"{cls.tr('carousel_item')} {index + 1}", "description": cls.tr("carousel_desc"), "image": sources[index % len(sources)]}
            for index in range(6)
        ] if sources else []
        carousel = CCarousel(items, num_visible=3)
        carousel.setMinimumHeight(340)
        return carousel

    @classmethod
    def _galleria_demo(cls) -> QWidget:
        sources = cls._images()
        items = [{"title": f"{cls.tr('gallery_item')} {index + 1}", "image": sources[index % len(sources)]} for index in range(4)] if sources else []
        galleria = CGalleria(items)
        galleria.setMinimumHeight(360)
        return galleria

    @classmethod
    def _file_demo(cls) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        advanced = CFileUpload(mode="advanced", accept=".jpg,.png,.svg,.pdf", max_file_size=5 * 1024 * 1024)
        basic = CFileUpload(mode="basic", accept=".jpg,.png,.svg,.pdf", multiple=False)
        status = QLabel(cls.tr("file_hint"))
        status.setStyleSheet("color: palette(midlight);")
        advanced.filesSelected.connect(lambda files: status.setText(f"{len(files)} {cls.tr('files')}"))
        basic.filesSelected.connect(lambda files: status.setText(f"{len(files)} {cls.tr('files')}"))
        for title_key, widget in (("file_advanced", advanced), ("file_basic", basic)):
            title = QLabel(cls.tr(title_key))
            title.setStyleSheet("color: palette(midlight); font-weight: 600;")
            layout.addWidget(title)
            layout.addWidget(widget)
        layout.addWidget(status)
        return box

    @classmethod
    def _chart_demo(cls) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        line = CChart("line", cls.tr("chart_title"))
        line.set_data([{"name": cls.tr("series"), "values": [12, 19, 14, 23, 18, 27], "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]}])
        line.setMinimumHeight(220)
        bar = CChart("bar", cls.tr("chart_bar"))
        bar.set_data([{"name": cls.tr("series"), "values": [7, 12, 9, 15], "labels": ["Q1", "Q2", "Q3", "Q4"]}])
        bar.setMinimumHeight(220)
        pie = CChart("pie", cls.tr("chart_pie"))
        pie.set_data([{"name": cls.tr("series"), "values": [40, 30, 20, 10], "labels": ["A", "B", "C", "D"]}])
        pie.setMinimumHeight(220)
        layout.addWidget(line)
        layout.addWidget(bar)
        layout.addWidget(pie)
        return box

    @classmethod
    def _misc_demo(cls) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        avatars = CAvatarGroup(["A", "B", "C", "D", "E"], max_count=4)
        icon_field = CIconField(placeholder=cls.tr("search_hint"), left_icon="icon_search", right_icon="icon_close")
        fluid = CFluid(icon_field)

        popup = CConfirmPopup(cls.tr("confirm_message"), cls.tr("yes"), cls.tr("no"))
        trigger = CButton(cls.tr("confirm_open"), variant="outlined", severity="warning")
        trigger.clicked.connect(lambda: popup.show_at(trigger))
        result = QLabel("")

        popup.accepted.connect(lambda: result.setText(cls.tr("accepted")))
        popup.rejected.connect(lambda: result.setText(cls.tr("rejected")))

        layout.addWidget(avatars)
        layout.addWidget(fluid, 1)
        layout.addWidget(trigger)
        layout.addWidget(result)
        return box

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_image"), cls._image_demo()),
            (cls.tr("group_carousel"), cls._carousel_demo()),
            (cls.tr("group_galleria"), cls._galleria_demo()),
            (cls.tr("group_file"), cls._file_demo()),
            (cls.tr("group_chart"), cls._chart_demo()),
            (cls.tr("group_misc"), cls._misc_demo()),
        ]


PAGE = MediaPreviewPage
