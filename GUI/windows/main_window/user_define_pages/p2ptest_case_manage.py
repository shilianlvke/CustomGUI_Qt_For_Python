"""模块说明。"""

from PySide6.QtCore import QMargins, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from AppCore import AppSettings, ColorPalette, Language, Logger, PathFactory
from guicore import CCard, CPushButton, CShowCard, CStatusButton
from guicore.CustomUI.div import CHDiv


class P2PTestCaseLibPage:
    """P2P 测试用例库页面定义。"""

    def load_page(self: object) -> None:
        """构建并注册测试用例库页面。

        返回:
        - None
        """
        page = QWidget()
        page.setObjectName("p2pTestCaseLibPage")
        self.ui.load_pages.pages.addWidget(page)

        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)

        P2PTestCaseLibPage._build_left_section(self, page_layout)
        right_back_layout = P2PTestCaseLibPage._build_right_container(self, page_layout)
        P2PTestCaseLibPage._build_top_section(self, right_back_layout)
        P2PTestCaseLibPage._build_filter_section(self, right_back_layout)
        P2PTestCaseLibPage._build_case_cards(self, right_back_layout)

    def _build_left_section(self, page_layout: QHBoxLayout) -> None:
        left_back_card = CCard()
        left_back_card.setMaximumWidth(144 + 10 + 5 + 5 - 2)
        left_back_layout = QVBoxLayout(left_back_card)
        left_back_layout.setContentsMargins(QMargins(2, 2, 2, 2))
        page_layout.addWidget(left_back_card)

        left_card = CCard()
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        left_card_layout.setContentsMargins(QMargins(0, 6, 0, 0))
        left_scroller_area = QScrollArea()
        left_scroller_area.setObjectName("widget_show_scroller_area")
        left_scroller_area.setWidget(left_card)
        left_scroller_area.setWidgetResizable(True)
        left_scroller_area.setStyleSheet(f"#widget_show_scroller_area{{background-color:{ColorPalette.custom_dark_three};}}")
        left_scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroller_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_back_layout.addWidget(left_scroller_area)

        label_1 = QLabel("测试库")
        case_lib_btn1 = CPushButton(
            size=QSize(144, 32),
            text="全部测试库",
            icon=QIcon(PathFactory.set_svg_icon("icon_all")),
        )
        case_lib_btn2 = CPushButton(
            size=QSize(144, 32),
            text="组织测试库",
            icon=QIcon(PathFactory.set_svg_icon("icon_tree")),
        )
        case_lib_btn3 = CPushButton(
            size=QSize(144, 32),
            text="团队测试库",
            icon=QIcon(PathFactory.set_svg_icon("icon_team")),
        )

        left_card_layout.addWidget(label_1)
        left_card_layout.addWidget(case_lib_btn1)
        left_card_layout.addWidget(case_lib_btn2)
        left_card_layout.addWidget(case_lib_btn3)

        case_lib_btn1.clicked.connect(lambda: Logger.info("点击了'全部测试库'"))
        case_lib_btn2.clicked.connect(lambda: Logger.info("点击了'组织测试库'"))
        case_lib_btn3.clicked.connect(lambda: Logger.info("点击了'团队测试库'"))

    def _build_right_container(self, page_layout: QHBoxLayout) -> QVBoxLayout:
        right_back_card = CCard()
        right_back_layout = QVBoxLayout(right_back_card)
        right_back_layout.setContentsMargins(QMargins(2, 2, 2, 2))
        right_back_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.addWidget(right_back_card)
        return right_back_layout

    def _build_top_section(self, right_back_layout: QVBoxLayout) -> None:
        right_top_card = CCard()
        right_top_layout = QHBoxLayout(right_top_card)
        right_top_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_back_layout.addWidget(right_top_card)

        label_4 = QLabel("全部测试库")
        font = QFont(AppSettings.family, AppSettings.title_size)
        label_4.setFont(font)
        case_lib_btn9 = CPushButton(
            size=QSize(144, 32),
            text="新建测试库",
            icon=QIcon(PathFactory.set_svg_icon("icon_add")),
        )

        right_top_layout.addWidget(label_4)
        right_top_layout.addStretch()
        right_top_layout.addWidget(case_lib_btn9)
        right_back_layout.addWidget(CHDiv())

        case_lib_btn9.clicked.connect(lambda: Logger.info("点击了'新建测试库'"))

    def _build_filter_section(self, right_back_layout: QVBoxLayout) -> None:
        right_middle_card = CCard()
        right_middle_layout = QHBoxLayout(right_middle_card)
        right_middle_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_middle_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right_back_layout.addWidget(right_middle_card)

        label_5 = QLabel("筛选:")
        case_lib_btn_a = CStatusButton(size=QSize(64, 32), text_negative="全部", text_positive="全部")
        case_lib_btn_b = CStatusButton(size=QSize(64, 32), text_negative="星标", text_positive="星标")
        case_lib_btn_c = CStatusButton(size=QSize(64, 32), text_negative="最近", text_positive="最近")
        right_middle_layout.addWidget(label_5)
        right_middle_layout.addWidget(case_lib_btn_a)
        right_middle_layout.addWidget(case_lib_btn_b)
        right_middle_layout.addWidget(case_lib_btn_c)
        right_back_layout.addWidget(CHDiv())

        case_lib_btn_a.clicked.connect(lambda: Logger.info("点击了'全部'"))
        case_lib_btn_b.clicked.connect(lambda: Logger.info("点击了'星标'"))
        case_lib_btn_c.clicked.connect(lambda: Logger.info("点击了'最近'"))

    def _build_case_cards(self, right_back_layout: QVBoxLayout) -> None:
        right_bottom_card = CCard()
        right_bottom_layout = QVBoxLayout(right_bottom_card)
        right_bottom_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_bottom_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        right_bottom_layout.setSpacing(0)

        right_bottom_scroller_area = QScrollArea()
        right_bottom_scroller_area.setWidget(right_bottom_card)
        right_bottom_scroller_area.setWidgetResizable(True)
        right_bottom_scroller_area.setStyleSheet(f"background-color:{ColorPalette.custom_dark_three};")
        right_bottom_scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_bottom_scroller_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_back_layout.addWidget(right_bottom_scroller_area)

        cards = [
            CShowCard(None, Language.custom_ui.sys_github, "功能测试库"),
            CShowCard(None, Language.custom_ui.sys_github, "性能测试库"),
            CShowCard(None, Language.custom_ui.sys_github, "硬件测试库"),
            CShowCard(None, Language.custom_ui.sys_github, "软件测试库1"),
            CShowCard(None, Language.custom_ui.sys_github, "软件测试库2"),
            CShowCard(None, Language.custom_ui.sys_github, "软件测试库3"),
            CShowCard(None, Language.custom_ui.sys_github, "软件测试库4"),
            CShowCard(None, Language.custom_ui.sys_github, "软件测试库5"),
        ]
        for card in cards:
            right_bottom_layout.addWidget(card)
