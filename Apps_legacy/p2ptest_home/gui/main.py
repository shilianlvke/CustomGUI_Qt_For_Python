"""P2PTester 首页应用（App: p2ptest_home）。

应用页面协议：导出 PAGE（含 load_page(window) 方法）。
"""

from PySide6.QtCore import QMargins, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvgWidgets import QSvgWidget
from GuiCore import CCard, CComboBox, CLineEdit, CPushButton, CDialog, CHDiv
from AppCore import PathFactory, AppSettings, Language

_LANG = "app.p2ptest_home"


def _t(key):
    return Language.resolve(f"{_LANG}.{key}", key)


class TeamCreateDialog:
    """创建团队对话框（p2ptest_home 应用内业务组件）。"""

    @staticmethod
    def setup_ui(title) -> None:
        create_team = CDialog(title)

        team_name = CCard()
        team_name_layout = QHBoxLayout(team_name)
        team_name_label = QLabel(_t("team_create_dialog.team_name_label"))
        team_name_line_edit = CLineEdit(place_holder_text=_t("team_create_dialog.team_name_input"))
        team_name_layout.addWidget(team_name_label)
        team_name_layout.addWidget(team_name_line_edit)

        team_doc = CCard()
        team_doc_layout = QHBoxLayout(team_doc)
        team_doc_label = QLabel(_t("team_create_dialog.team_doc_label"))
        team_doc_line_edit = CLineEdit(place_holder_text=_t("team_create_dialog.team_doc_input"))
        team_doc_layout.addWidget(team_doc_label)
        team_doc_layout.addWidget(team_doc_line_edit)

        team_submit = CCard()
        team_submit_layout = QVBoxLayout(team_submit)
        team_submit_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        team_submit_btn = CPushButton(
            size=QSize(192, 32),
            text=_t("team_create_dialog.team_create_btn"),
            icon=QIcon(PathFactory.set_svg_icon("icon_new_build")),
        )
        team_submit_layout.addWidget(team_submit_btn)

        create_team.content_layout.addWidget(team_name)
        create_team.content_layout.addWidget(team_doc)
        create_team.content_layout.addStretch()
        create_team.content_layout.addWidget(team_submit)
        create_team.setModal(True)
        create_team.show()
        create_team.exec()


class TeamSearchDialog:
    """搜索团队对话框（p2ptest_home 应用内业务组件）。"""

    @staticmethod
    def setup_ui(title) -> None:
        create_team = CDialog(title)

        team_name = CCard()
        team_name_layout = QHBoxLayout(team_name)
        team_name_label = QLabel(_t("team_create_dialog.team_name_label"))
        team_name_line_edit = CLineEdit(place_holder_text=_t("team_create_dialog.team_name_input"))
        team_name_layout.addWidget(team_name_label)
        team_name_layout.addWidget(team_name_line_edit)

        team_doc = CCard()
        team_doc_layout = QHBoxLayout(team_doc)
        team_doc_label = QLabel(_t("team_create_dialog.team_doc_label"))
        team_doc_line_edit = CLineEdit(place_holder_text=_t("team_create_dialog.team_doc_input"))
        team_doc_layout.addWidget(team_doc_label)
        team_doc_layout.addWidget(team_doc_line_edit)

        team_submit = CCard()
        team_submit_layout = QVBoxLayout(team_submit)
        team_submit_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        team_submit_btn = CPushButton(
            size=QSize(192, 32),
            text=_t("team_create_dialog.team_create_btn"),
            icon=QIcon(PathFactory.set_svg_icon("icon_new_build")),
        )
        team_submit_layout.addWidget(team_submit_btn)

        create_team.content_layout.addWidget(team_name)
        create_team.content_layout.addWidget(team_doc)
        create_team.content_layout.addStretch()
        create_team.content_layout.addWidget(team_submit)
        create_team.setModal(True)
        create_team.show()
        create_team.exec()


class P2PTestHomePage:
    def load_page(self):
        # 新增页面
        page = QWidget()
        page.setObjectName("p2pTestHomePage")
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

        welcome_card = CCard()
        page_card_layout.addWidget(welcome_card)
        welcome_card_layout = QHBoxLayout(welcome_card)
        welcome_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))

        logo_svg = QSvgWidget(PathFactory.set_svg_image(AppSettings.logo_home))
        logo_svg.setFixedSize(QSize(64, 64))
        welcome_card_layout.addWidget(logo_svg)

        welcome_label = QLabel(Language.custom_ui.sys_copyright)
        welcome_label.setStyleSheet(f'font: 700 20pt "{AppSettings.family}";')
        welcome_card_layout.addWidget(welcome_label)

        page_card_layout.addWidget(CHDiv())
        page_card_layout.addStretch()

        login_card = CCard()
        login_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        login_card_layout = QVBoxLayout(login_card)
        login_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        login_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        login_card_layout.setSpacing(3)
        page_card_layout.addWidget(login_card)

        username_card = CCard()
        username_card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        username_card_layout = QHBoxLayout(username_card)
        username_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        username_card_layout.setSpacing(0)
        username_label = QLabel(Language.resolve(f"{_LANG}.login.username"))
        username_label.setMinimumWidth(100)
        username_line_edit = CLineEdit(place_holder_text=Language.resolve(f"{_LANG}.login.input_username"))
        username_line_edit.setMinimumWidth(150)
        username_card_layout.addWidget(username_label)
        username_card_layout.addWidget(username_line_edit)
        login_card_layout.addWidget(username_card)
        login_card_layout.addWidget(CHDiv())

        userpass_card = CCard()
        userpass_card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        userpass_card_layout = QHBoxLayout(userpass_card)
        userpass_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        userpass_card_layout.setSpacing(0)
        userpass_label = QLabel(Language.resolve(f"{_LANG}.login.password"))
        userpass_label.setMinimumWidth(100)
        userpass_line_edit = CLineEdit(place_holder_text=Language.resolve(f"{_LANG}.login.input_password"))
        userpass_line_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        userpass_line_edit.setMinimumWidth(150)
        userpass_card_layout.addWidget(userpass_label)
        userpass_card_layout.addWidget(userpass_line_edit)
        login_card_layout.addWidget(userpass_card)
        login_card_layout.addWidget(CHDiv())

        test_node_card = CCard()
        test_node_card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        test_node_card_layout = QHBoxLayout(test_node_card)
        test_node_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        test_node_card_layout.setSpacing(0)
        test_node_label = QLabel(Language.resolve(f"{_LANG}.login.test_team"))
        test_node_label.setMinimumWidth(100)
        test_node_line_combox = CComboBox(
            size=QSize(120, 32),
            items=["xxx功能测试", "xxx性能测试", "xxx外观测试"],
            placeholder_text=Language.resolve(f"{_LANG}.login.team_combox_tooltip"),
        )
        test_node_line_combox.setMinimumWidth(150)
        test_node_card_layout.addWidget(test_node_label)
        test_node_card_layout.addWidget(test_node_line_combox)
        login_card_layout.addWidget(test_node_card)
        login_card_layout.addWidget(CHDiv())

        login_btn_card = CCard()
        login_btn_card_layout = QHBoxLayout(login_btn_card)
        login_btn_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        login_btn_card_layout.setSpacing(0)
        login_btn = CPushButton(
            size=QSize(150, 32),
            text=Language.resolve(f"{_LANG}.login.btn_login"),
            icon=QIcon(PathFactory.set_svg_icon("icon_login")),
        )
        login_btn_card_layout.addWidget(login_btn)
        login_card_layout.addWidget(login_btn_card)

        page_card_layout.addStretch()
        page_card_layout.addWidget(CHDiv())

        init_card = CCard()
        init_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        init_card_layout = QGridLayout(init_card)
        init_card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        init_card_layout.setSpacing(0)
        init_card_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        init_create_btn = CPushButton(
            size=QSize(192, 32),
            text=Language.resolve(f"{_LANG}.login.team_create"),
            icon=QIcon(PathFactory.set_svg_icon("icon_add")),
        )
        init_search_btn = CPushButton(
            size=QSize(192, 32),
            text=Language.resolve(f"{_LANG}.login.team_search"),
            icon=QIcon(PathFactory.set_svg_icon("icon_search")),
        )
        init_card_layout.addWidget(init_create_btn, 0, 0)
        init_card_layout.addWidget(init_search_btn, 1, 0)
        page_card_layout.addWidget(init_card)

        init_create_btn.clicked.connect(
            lambda x: TeamCreateDialog.setup_ui(Language.resolve(f"{_LANG}.login.team_create_window"))
        )
        init_search_btn.clicked.connect(
            lambda x: TeamSearchDialog.setup_ui(Language.resolve(f"{_LANG}.login.team_search_window"))
        )


PAGE = P2PTestHomePage
