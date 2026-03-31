"""模块说明。"""

from PySide6.QtCore import QMargins, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from AppCore import AppSettings, ColorPalette, Language, Logger, PathFactory
from guicore import CCard, CPushButton, CShowCard, CStatusButton
from guicore.CustomUI.div import CHDiv


class P2PTestReportPage:
    """P2P 测试报告页面定义。"""

    def load_page(self: object) -> None:
        """构建并注册测试报告页面。

        返回:
        - None
        """
        # 新增页面
        page = QWidget()
        page.setObjectName("p2pTestReportPage")
        self.ui.load_pages.pages.addWidget(page)
        # 绘制页面
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)

        right_back_layout = P2PTestReportPage._build_right_container(self, page_layout)
        P2PTestReportPage._build_top_section(self, right_back_layout)
        P2PTestReportPage._build_filter_section(self, right_back_layout)
        P2PTestReportPage._build_report_cards(self, right_back_layout)

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

        label_4 = QLabel("全部测试报告")
        font = QFont(AppSettings.family, AppSettings.title_size)
        label_4.setFont(font)

        case_lib_btn9 = CPushButton(
            size=QSize(144, 32), text="新建测试报告", icon=QIcon(PathFactory.set_svg_icon("icon_add")),
        )

        right_top_layout.addWidget(label_4)
        right_top_layout.addStretch()
        right_top_layout.addWidget(case_lib_btn9)
        right_back_layout.addWidget(CHDiv())
        case_lib_btn9.clicked.connect(lambda: Logger.info("点击了'新建测试报告'"))

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

    def _build_report_cards(self, right_back_layout: QVBoxLayout) -> None:
        right_bottom_card = CCard()
        right_bottom_layout = QGridLayout(right_bottom_card)
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
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "功能测试报告"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "性能测试报告"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "硬件测试报告"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告1"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告2"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告3"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告4"),
            CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告5"),
        ]
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1)]
        for card, (row, col) in zip(cards, positions, strict=False):
            right_bottom_layout.addWidget(card, row, col)
