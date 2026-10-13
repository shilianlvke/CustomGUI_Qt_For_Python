from PySide6.QtCore import Qt, QMargins, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QHBoxLayout
from GuiCore import CCard, CPushButton, CScrollArea, CShowCard, CStatusButton
from AppCore import PathFactory, ColorPalette, Logger, AppSettings, Language
from GuiCore.CustomUI.div import CHDiv

_LANG = "app.p2ptest_case_lib"


def _t(key):
    return Language.resolve(f"{_LANG}.{key}", key)


class P2PTestCaseLibPage:

    def load_page(self):
        # 新增页面
        page = QWidget()
        page.setObjectName("p2pTestCaseLibPage")
        self.ui.load_pages.pages.addWidget(page)
        # 绘制页面
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)

        left_back_card = CCard()
        left_back_card.setMaximumWidth(144 + 10 + 5 + 5 - 2)
        left_back_layout = QVBoxLayout(left_back_card)
        left_back_layout.setContentsMargins(QMargins(2, 2, 2, 2))
        page_layout.addWidget(left_back_card)

        left_card = CCard()
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        left_card_layout.setContentsMargins(QMargins(0, 6, 0, 0))
        left_scroller_area = CScrollArea()
        left_scroller_area.setObjectName("widget_show_scroller_area")
        left_scroller_area.setWidget(left_card)
        left_scroller_area.setWidgetResizable(True)
        left_scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroller_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_back_layout.addWidget(left_scroller_area)

        label_1 = QLabel(_t("lib_title"))

        case_lib_btn1 = CPushButton(
            size=QSize(144, 32), text=_t("all_lib"), icon=QIcon(PathFactory.set_svg_icon("icon_all"))
        )
        case_lib_btn2 = CPushButton(
            size=QSize(144, 32), text=_t("org_lib"), icon=QIcon(PathFactory.set_svg_icon("icon_tree"))
        )
        case_lib_btn3 = CPushButton(
            size=QSize(144, 32), text=_t("team_lib"), icon=QIcon(PathFactory.set_svg_icon("icon_team"))
        )

        left_card_layout.addWidget(label_1)
        left_card_layout.addWidget(case_lib_btn1)
        left_card_layout.addWidget(case_lib_btn2)
        left_card_layout.addWidget(case_lib_btn3)

        case_lib_btn1.clicked.connect(lambda: Logger.info("点击了'全部测试库'"))
        case_lib_btn2.clicked.connect(lambda: Logger.info("点击了'组织测试库'"))
        case_lib_btn3.clicked.connect(lambda: Logger.info("点击了'团队测试库'"))

        right_back_card = CCard()
        right_back_layout = QVBoxLayout(right_back_card)
        right_back_layout.setContentsMargins(QMargins(2, 2, 2, 2))
        right_back_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.addWidget(right_back_card)

        # layout
        right_top_card = CCard()
        right_top_layout = QHBoxLayout(right_top_card)
        right_top_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_back_layout.addWidget(right_top_card)

        label_4 = QLabel(_t("all_lib"))
        font = QFont(AppSettings.family, AppSettings.title_size)
        label_4.setFont(font)

        case_lib_btn9 = CPushButton(
            size=QSize(144, 32), text=_t("new_lib"), icon=QIcon(PathFactory.set_svg_icon("icon_add"))
        )

        right_top_layout.addWidget(label_4)
        right_top_layout.addStretch()
        right_top_layout.addWidget(case_lib_btn9)
        right_back_layout.addWidget(CHDiv())

        case_lib_btn9.clicked.connect(lambda: Logger.info("点击了'新建测试库'"))

        right_middle_card = CCard()
        right_middle_layout = QHBoxLayout(right_middle_card)
        right_middle_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_middle_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right_back_layout.addWidget(right_middle_card)

        label_5 = QLabel(_t("filter"))

        case_lib_btnA = CStatusButton(size=QSize(64, 32), text_negative=_t("filter_all"), text_positive=_t("filter_all"))
        case_lib_btnB = CStatusButton(size=QSize(64, 32), text_negative=_t("filter_star"), text_positive=_t("filter_star"))
        case_lib_btnC = CStatusButton(size=QSize(64, 32), text_negative=_t("filter_recent"), text_positive=_t("filter_recent"))
        right_middle_layout.addWidget(label_5)
        right_middle_layout.addWidget(case_lib_btnA)
        right_middle_layout.addWidget(case_lib_btnB)
        right_middle_layout.addWidget(case_lib_btnC)
        right_back_layout.addWidget(CHDiv())

        case_lib_btnA.clicked.connect(lambda: Logger.info("点击了'全部'"))
        case_lib_btnB.clicked.connect(lambda: Logger.info("点击了'星标'"))
        case_lib_btnC.clicked.connect(lambda: Logger.info("点击了'最近'"))

        right_bottom_card = CCard()
        right_bottom_layout = QVBoxLayout(right_bottom_card)
        right_bottom_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_bottom_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        right_bottom_layout.setSpacing(0)

        right_bottom_scroller_area = CScrollArea()
        right_bottom_scroller_area.setWidget(right_bottom_card)
        right_bottom_scroller_area.setWidgetResizable(True)
        right_bottom_scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_bottom_scroller_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_back_layout.addWidget(right_bottom_scroller_area)

        card_1 = CShowCard(None, Language.custom_ui.sys_github, _t("card_func_lib"))
        card_2 = CShowCard(None, Language.custom_ui.sys_github, _t("card_perf_lib"))
        card_3 = CShowCard(None, Language.custom_ui.sys_github, _t("card_hw_lib"))
        card_4 = CShowCard(None, Language.custom_ui.sys_github, _t("card_sw_lib_1"))
        card_5 = CShowCard(None, Language.custom_ui.sys_github, _t("card_sw_lib_2"))
        card_6 = CShowCard(None, Language.custom_ui.sys_github, _t("card_sw_lib_3"))
        card_7 = CShowCard(None, Language.custom_ui.sys_github, _t("card_sw_lib_4"))
        card_8 = CShowCard(None, Language.custom_ui.sys_github, _t("card_sw_lib_5"))
        right_bottom_layout.addWidget(card_1)
        right_bottom_layout.addWidget(card_2)
        right_bottom_layout.addWidget(card_3)
        right_bottom_layout.addWidget(card_4)
        right_bottom_layout.addWidget(card_5)
        right_bottom_layout.addWidget(card_6)
        right_bottom_layout.addWidget(card_7)
        right_bottom_layout.addWidget(card_8)


PAGE = P2PTestCaseLibPage

