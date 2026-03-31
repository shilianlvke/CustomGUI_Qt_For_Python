"""模块说明。"""

from AppCore import ColorPalette, Language, Logger, PathFactory
from guicore import CCard, CComboBox, CMenu, CMenuButton, CPushButton, CShowCard, CStatusButton
from qt_core import (
    QGridLayout,
    QIcon,
    QMargins,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)


class NormalWidgetShowPage:
    """组件展示页定义。"""

    def load_page(self: object) -> None:
        """构建并注册组件展示页面。

        返回:
        - None
        """
        page = QWidget()
        page.setObjectName("normalWidgetShowPage")
        self.ui.load_pages.pages.addWidget(page)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome_card_layout = NormalWidgetShowPage._build_page_layout(self, page_layout)
        cards = NormalWidgetShowPage._create_demo_cards(self)
        positions = [
            (cards[0], 0, 0),
            (cards[1], 0, 1),
            (cards[2], 0, 2),
            (cards[3], None, None),
            (cards[4], None, None),
            (cards[5], None, None),
            (cards[6], None, None),
        ]
        for card, row, col in positions:
            if row is None or col is None:
                welcome_card_layout.addWidget(card)
            else:
                welcome_card_layout.addWidget(card, row, col)

    def _build_page_layout(self, page_layout: QVBoxLayout) -> QGridLayout:
        page_card = CCard()
        page_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page_card_layout = QVBoxLayout(page_card)
        page_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(page_card)

        card = CCard()
        page_card_layout.addWidget(card)
        welcome_card_layout = QGridLayout(card)
        welcome_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))

        scroller_area = QScrollArea()
        scroller_area.setObjectName("widget_show_scroller_area")
        scroller_area.setWidget(card)
        scroller_area.setWidgetResizable(True)
        scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller_area.setStyleSheet(f"#widget_show_scroller_area{{background-color:{ColorPalette.custom_dark_three};}}")
        page_card_layout.addWidget(scroller_area)
        return welcome_card_layout

    def _create_demo_cards(self) -> list[CShowCard]:
        stander_btn = CPushButton(text="标准按钮")
        stander_btn.clicked.connect(lambda: Logger.info("点击了标准按钮"))
        icon_btn = CPushButton(size=QSize(64, 64), icon=PathFactory.set_jpg_image("托盘"))
        icon_btn.clicked.connect(lambda: Logger.info("点击了图片按钮"))
        text_icon_btn = CPushButton(
            size=QSize(128, 32),
            icon=QIcon(PathFactory.set_svg_icon("icon_heart")),
            text="QIcon-文字按钮",
        )
        text_icon_btn.clicked.connect(lambda: Logger.info("点击了文字按钮"))
        two_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative="左",
            text_positive="右",
        )
        two_btn.clicked.connect(lambda: Logger.info(f"点击了双态按钮当前状态{two_btn.status}"))
        three_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_down")),
            icon_normal=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative="中",
            text_normal="左",
            text_positive="右",
            is_normal=True,
        )
        three_btn.clicked.connect(lambda: Logger.info(f"点击了三态按钮当前状态{three_btn.status}"))
        menu_btn = CMenuButton(
            colorpalette=ColorPalette,
            text="邮件",
            icon=QIcon(PathFactory.set_svg_icon("icon_mail")),
        )
        menu_btn.clicked.connect(lambda: Logger.info("点击了菜单按钮"))
        menu = CMenu(self, colorpalette=ColorPalette)
        f1 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_save")), "保存")
        f2 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_mail_send")), "发送")
        f1.triggered.connect(lambda: Logger.info("点击了菜单按钮保存"))
        f2.triggered.connect(lambda: Logger.info("点击了菜单按钮发送"))
        menu_btn.setMenu(menu)
        combo_box_0 = CComboBox(size=QSize(120, 30), items=["提莫", "亚索", "阿狸"], placeholder_text="选择你的英雄")
        combo_box_0.currentIndexChanged.connect(lambda: Logger.info(f"改变了下拉框值{combo_box_0.currentIndex()}"))

        github_url = Language.custom_ui.sys_github
        return [
            CShowCard(None, github_url, "标准按钮", stander_btn),
            CShowCard(None, github_url, "图标按钮", icon_btn),
            CShowCard(None, github_url, "QIcon-文字按钮", text_icon_btn),
            CShowCard(None, github_url, "双态按钮", two_btn),
            CShowCard(None, github_url, "三态按钮", three_btn),
            CShowCard(None, github_url, "菜单按钮", menu_btn),
            CShowCard(None, github_url, "下拉框", combo_box_0),
        ]
