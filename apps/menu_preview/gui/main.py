"""菜单与步骤预览页：Menubar / TieredMenu / MegaMenu / PanelMenu / ContextMenu / TabMenu / Stepper。"""

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, Language
from customgui.guicore import (
    CButton,
    CCard,
    CContextMenu,
    CMegaMenu,
    CMenubar,
    CPanelMenu,
    CScrollArea,
    CStepper,
    CTabMenu,
    CTieredMenu,
)

_LANG = "app.menu_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _items() -> list[dict]:
    return [
        {
            "label": _t("menu_file"),
            "items": [
                {"label": _t("menu_new"), "icon": "icon_add", "key": "new"},
                {"label": _t("menu_open"), "icon": "icon_books", "key": "open"},
                {"separator": True},
                {"label": _t("menu_save"), "icon": "icon_save", "key": "save"},
            ],
        },
        {
            "label": _t("menu_edit"),
            "items": [
                {"label": _t("menu_copy"), "key": "copy"},
                {"label": _t("menu_paste"), "key": "paste"},
            ],
        },
        {"label": _t("menu_view"), "key": "view"},
    ]


def _nested_items() -> list[dict]:
    return [
        {
            "label": _t("menu_components"),
            "icon": "icon_widget",
            "items": [
                {"label": "DataTable", "key": "table"},
                {
                    "label": _t("menu_forms"),
                    "items": [
                        {"label": "InputText", "key": "input"},
                        {"label": "Select", "key": "select"},
                    ],
                },
                {"label": "Tree", "key": "tree"},
            ],
        },
        {
            "label": _t("menu_pages"),
            "icon": "icon_home",
            "items": [
                {"label": _t("menu_dashboard"), "key": "dashboard"},
                {"label": _t("menu_settings"), "key": "settings"},
            ],
        },
        {"label": _t("menu_disabled"), "disabled": True},
    ]


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


def _menubar_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    bar = CMenubar(_items())
    status = QLabel(_t("menu_hint"))
    status.setStyleSheet("color: palette(mid);")
    bar.itemClicked.connect(lambda item: status.setText(f"{_t('clicked')}: {getattr(item, 'label', item)}"))
    layout.addWidget(bar)
    layout.addWidget(status)
    layout.addStretch(1)
    return box


def _tiered_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    menu = CTieredMenu(_nested_items())
    status = QLabel(_t("menu_hint"))
    status.setStyleSheet("color: palette(mid);")
    menu.itemClicked.connect(lambda item: status.setText(f"{_t('clicked')}: {getattr(item, 'label', item)}"))
    layout.addWidget(menu, 0, Qt.AlignLeft)
    layout.addWidget(status)
    return box


def _mega_demo() -> QWidget:
    menu = CMegaMenu(_items(), columns=2)
    menu.setMinimumHeight(260)
    return menu


def _panel_demo() -> QWidget:
    menu = CPanelMenu(_nested_items())
    menu.setMinimumHeight(300)
    return menu


def _context_demo() -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    menu = CContextMenu(_items())
    status = QLabel(_t("context_hint"))
    status.setStyleSheet("color: palette(mid);")
    menu.itemClicked.connect(lambda item: status.setText(f"{_t('clicked')}: {getattr(item, 'label', item)}"))

    trigger = CButton(_t("open_context"), icon="icon_menu", variant="outlined")
    trigger.clicked.connect(lambda: menu.show_at(trigger.mapToGlobal(trigger.rect().bottomLeft())))
    layout.addWidget(trigger)
    layout.addWidget(status, 1)
    return box


def _tab_menu_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    tabs = CTabMenu([_t("tab_home"), _t("tab_components"), _t("tab_settings")])
    content = QLabel(_t("tab_content"))
    content.setStyleSheet("color: palette(mid);")
    tabs.tabChanged.connect(lambda index: content.setText(f"{_t('tab_selected')}: {tabs.tabs()[index]}"))
    layout.addWidget(tabs)
    layout.addWidget(content)
    return box


def _stepper_demo() -> QWidget:
    steps = []
    for index in range(1, 4):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 12, 0, 12)
        page_layout.addWidget(QLabel(_t(f"step_{index}_body")))
        steps.append((_t(f"step_{index}"), page))
    stepper = CStepper(steps)
    stepper.setMinimumHeight(220)
    return stepper


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("menuPreviewPage")
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

    for title, widget in (
        (_t("group_menubar"), _menubar_demo()),
        (_t("group_tiered"), _tiered_demo()),
        (_t("group_mega"), _mega_demo()),
        (_t("group_panel"), _panel_demo()),
        (_t("group_context"), _context_demo()),
        (_t("group_tabmenu"), _tab_menu_demo()),
        (_t("group_stepper"), _stepper_demo()),
    ):
        layout.addWidget(_card(title, widget))
    layout.addStretch()
    return page


class MenuPreviewPage:
    """PAGE 协议入口。"""

    def load_page(self):
        _build_page(self)


PAGE = MenuPreviewPage
