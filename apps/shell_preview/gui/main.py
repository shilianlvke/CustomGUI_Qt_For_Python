"""Sakai 壳层预览页：顶栏、嵌套侧边菜单与主题配置抽屉。"""

from PySide6.QtCore import QMargins
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, Language
from customgui.guicore import (
    CAppConfigurator,
    CAppMenu,
    CAppTopbar,
    CButton,
    CCard,
    CScrollArea,
)

_LANG = "app.shell_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


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


def _menu_items() -> list[dict]:
    return [
        {
            "label": _t("group_ui"),
            "icon": "icon_widget",
            "items": [
                {"label": "DataTable", "key": "table"},
                {"label": "List", "key": "list"},
                {
                    "label": _t("group_forms"),
                    "items": [
                        {"label": "InputText", "key": "input"},
                        {"label": "Select", "key": "select"},
                    ],
                },
            ],
        },
        {
            "label": _t("group_pages"),
            "icon": "icon_home",
            "items": [
                {"label": _t("menu_dashboard"), "key": "dashboard"},
                {"label": _t("menu_settings"), "key": "settings"},
            ],
        },
    ]


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("shellPreviewPage")
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

    topbar = CAppTopbar(title="Sakai Shell", logo="mihoutao")
    topbar.set_user("Y")
    topbar.set_unread_count(3)
    status = QLabel(_t("hint"))
    status.setStyleSheet("color: palette(mid);")
    topbar.searchChanged.connect(lambda text: status.setText(f"{_t('search')}: {text}"))
    topbar.notificationsClicked.connect(lambda: status.setText(_t("notifications")))
    topbar.userMenuRequested.connect(lambda: status.setText(_t("user_menu")))

    menu = CAppMenu(_menu_items())
    menu.setMinimumWidth(280)
    menu.itemClicked.connect(lambda item: status.setText(f"{_t('menu_selected')}: {getattr(item, 'label', item)}"))

    configurator = CAppConfigurator(page)
    configurator.setVisible(False)
    configurator.themeChanged.connect(lambda name: status.setText(f"{_t('theme')}: {name}"))

    trigger = CButton(_t("open_config"), icon="icon_config", variant="outlined")
    trigger.clicked.connect(configurator.toggle)

    topbar_card = _card(_t("group_topbar"), topbar)
    menu_card = _card(_t("group_menu"), menu)
    config_card = _card(_t("group_config"), trigger)

    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    row_layout.addWidget(menu_card, 2)
    right = QVBoxLayout()
    right.setContentsMargins(0, 0, 0, 0)
    right.setSpacing(6)
    right.addWidget(config_card)
    right.addWidget(status)
    right.addStretch(1)
    row_layout.addLayout(right, 3)

    layout.addWidget(topbar_card)
    layout.addWidget(row)
    layout.addStretch()
    page._shell_configurator = configurator
    return page


class ShellPreviewPage:
    """PAGE 协议入口。"""

    def load_page(self):
        _build_page(self)


PAGE = ShellPreviewPage
