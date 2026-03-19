from PySide6.QtCore import Qt, QMargins, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QGridLayout, QScrollArea, QHBoxLayout
from GuiCore import CCard, CPushButton, CShowCard, CStatusButton
from AppCore import PathFactory, ColorPalette, Logger, AppSettings, Language
from GuiCore.CustomUI.div import CHDiv


class P2PTestReportPage:

    def load_page(self):
        # 新增页面
        page = QWidget()
        page.setObjectName("p2pTestReportPage")
        self.ui.load_pages.pages.addWidget(page)
        # 绘制页面
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.setSpacing(3)

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

        label_4 = QLabel("全部测试报告")
        font = QFont(AppSettings.family, AppSettings.title_size)
        label_4.setFont(font)

        case_lib_btn9 = CPushButton(size=QSize(144, 32), text="新建测试报告", icon=QIcon(PathFactory.set_svg_icon("icon_add")))

        right_top_layout.addWidget(label_4)
        right_top_layout.addStretch()
        right_top_layout.addWidget(case_lib_btn9)
        right_back_layout.addWidget(CHDiv())

        case_lib_btn9.clicked.connect(lambda: Logger.info("点击了'新建测试报告'"))

        right_middle_card = CCard()
        right_middle_layout = QHBoxLayout(right_middle_card)
        right_middle_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_middle_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right_back_layout.addWidget(right_middle_card)

        label_5 = QLabel("筛选:")

        case_lib_btnA = CStatusButton(size=QSize(64, 32), text_negative="全部", text_positive="全部")
        case_lib_btnB = CStatusButton(size=QSize(64, 32), text_negative="星标", text_positive="星标")
        case_lib_btnC = CStatusButton(size=QSize(64, 32), text_negative="最近", text_positive="最近")
        right_middle_layout.addWidget(label_5)
        right_middle_layout.addWidget(case_lib_btnA)
        right_middle_layout.addWidget(case_lib_btnB)
        right_middle_layout.addWidget(case_lib_btnC)
        right_back_layout.addWidget(CHDiv())

        case_lib_btnA.clicked.connect(lambda: Logger.info("点击了'全部'"))
        case_lib_btnB.clicked.connect(lambda: Logger.info("点击了'星标'"))
        case_lib_btnC.clicked.connect(lambda: Logger.info("点击了'最近'"))

        right_bottom_card = CCard()
        right_bottom_layout = QGridLayout(right_bottom_card)
        right_bottom_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        right_bottom_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        right_bottom_layout.setSpacing(0)

        right_bottom_scroller_area = QScrollArea()
        right_bottom_scroller_area.setWidget(right_bottom_card)
        right_bottom_scroller_area.setWidgetResizable(True)
        right_bottom_scroller_area.setStyleSheet(f"background:{ColorPalette.custom_dark_three};")
        right_bottom_scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_bottom_scroller_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_back_layout.addWidget(right_bottom_scroller_area)

        card_1 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "功能测试报告")
        card_2 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "性能测试报告")
        card_3 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "硬件测试报告")
        card_4 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告1")
        card_5 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告2")
        card_6 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告3")
        card_7 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告4")
        card_8 = CShowCard(QSize(230, 128), Language.custom_ui.sys_github, "软件测试报告5")
        right_bottom_layout.addWidget(card_1, 0, 0)
        right_bottom_layout.addWidget(card_2, 0, 1)
        right_bottom_layout.addWidget(card_3, 0, 2)
        right_bottom_layout.addWidget(card_4, 1, 0)
        right_bottom_layout.addWidget(card_5, 1, 1)
        right_bottom_layout.addWidget(card_6, 1, 2)
        right_bottom_layout.addWidget(card_7, 2, 0)
        right_bottom_layout.addWidget(card_8, 2, 1)
