from qt_core import (
    QGridLayout,
    QIcon,
    QMargins,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
)
from GuiCore import CCard, CComboBox, CStatusButton, CPushButton, CMenuButton, CMenu, CScrollArea, CShowCard
from AppCore import PathFactory, Language, Logger, ColorPalette


def _t(key):
    """读取欢迎页语言键（load_page 的 self 是 window，故用模块级函数）。"""
    return Language.resolve(f"PAGE.widget_show.{key}", key)


class NormalWidgetShowPage:
    """基座欢迎页（组件展示）：全部可见文本走语言包，语言切换时随页面重建刷新。"""

    def load_page(self):
        # 新增页面
        page = QWidget()
        page.setObjectName("normalWidgetShowPage")
        self.ui.load_pages.pages.addWidget(page)
        # 绘制页面
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        page_card = CCard()
        page_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page_card_layout = QVBoxLayout(page_card)
        page_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(page_card)

        Card = CCard()
        page_card_layout.addWidget(Card)
        welcome_card_layout = QGridLayout(Card)
        welcome_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))

        scroller_area = CScrollArea(object_name="widget_show_scroller_area")
        scroller_area.setWidget(Card)
        scroller_area.setWidgetResizable(True)
        scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page_card_layout.addWidget(scroller_area)

        stander_btn = CPushButton(text=_t("btn_standard"))
        stander_btn.clicked.connect(lambda: Logger.info("点击了标准按钮"))
        icon_btn = CPushButton(size=QSize(64, 64), icon=PathFactory.set_jpg_image("托盘"))
        icon_btn.clicked.connect(lambda: Logger.info("点击了图片按钮"))
        text_icon_btn = CPushButton(
            size=QSize(128, 32), icon=QIcon(PathFactory.set_svg_icon("icon_heart")), text=_t("btn_text_icon")
        )
        text_icon_btn.clicked.connect(lambda: Logger.info("点击了文字按钮"))
        two_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative=_t("state_left"),
            text_positive=_t("state_right"),
        )
        two_btn.clicked.connect(lambda: Logger.info(f"点击了双态按钮当前状态{two_btn.status}"))
        three_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_down")),
            icon_normal=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative=_t("state_middle"),
            text_normal=_t("state_left"),
            text_positive=_t("state_right"),
            is_normal=True,
        )
        three_btn.clicked.connect(lambda: Logger.info(f"点击了三态按钮当前状态{three_btn.status}"))
        menu_btn = CMenuButton(
            colorpalette=ColorPalette,
            text=_t("menu_mail"),
            icon=QIcon(PathFactory.set_svg_icon("icon_mail")),
        )
        menu_btn.clicked.connect(lambda: Logger.info("点击了菜单按钮"))
        menu = CMenu(self, colorpalette=ColorPalette)
        f1 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_save")), _t("menu_save"))
        f2 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_mail_send")), _t("menu_send"))
        f1.triggered.connect(lambda: Logger.info("点击了菜单按钮保存"))
        f2.triggered.connect(lambda: Logger.info("点击了菜单按钮发送"))
        menu_btn.setMenu(menu)
        combo_box_0 = CComboBox(
            size=QSize(120, 30),
            items=["提莫", "亚索", "阿狸"],
            placeholder_text=_t("combo_placeholder"),
        )
        combo_box_0.currentIndexChanged.connect(lambda: Logger.info(f"改变了下拉框值{combo_box_0.currentIndex()}"))
        card_1 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_standard"), stander_btn)
        card_2 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_icon"), icon_btn)
        card_4 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_text_icon"), text_icon_btn)
        card_5 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_two_state"), two_btn)
        card_6 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_three_state"), three_btn)
        card_7 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_menu"), menu_btn)
        card_8 = CShowCard(None, Language.custom_ui.sys_github, _t("btn_combo"), combo_box_0)
        welcome_card_layout.addWidget(card_1, 0, 0)
        welcome_card_layout.addWidget(card_2, 0, 1)
        welcome_card_layout.addWidget(card_4, 0, 2)
        welcome_card_layout.addWidget(card_5)
        welcome_card_layout.addWidget(card_6)
        welcome_card_layout.addWidget(card_7)
        welcome_card_layout.addWidget(card_8)
