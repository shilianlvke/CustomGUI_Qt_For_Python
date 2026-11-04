"""菜单与步骤预览页：Menubar / TieredMenu / MegaMenu / PanelMenu / ContextMenu / TabMenu / Stepper。"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.guicore import (
    CButton,
    CContextMenu,
    CMegaMenu,
    CMenubar,
    CPanelMenu,
    CPreviewPage,
    CStepper,
    CTabMenu,
    CTieredMenu,
)


class MenuPreviewPage(CPreviewPage):
    """PAGE 协议入口：七类菜单/步骤组件。"""

    slug = "menu_preview"

    @classmethod
    def _items(cls) -> list[dict]:
        return [
            {
                "label": cls.tr("menu_file"),
                "items": [
                    {"label": cls.tr("menu_new"), "icon": "icon_add", "key": "new"},
                    {"label": cls.tr("menu_open"), "icon": "icon_books", "key": "open"},
                    {"separator": True},
                    {"label": cls.tr("menu_save"), "icon": "icon_save", "key": "save"},
                ],
            },
            {
                "label": cls.tr("menu_edit"),
                "items": [
                    {"label": cls.tr("menu_copy"), "key": "copy"},
                    {"label": cls.tr("menu_paste"), "key": "paste"},
                ],
            },
            {"label": cls.tr("menu_view"), "key": "view"},
        ]

    @classmethod
    def _nested_items(cls) -> list[dict]:
        return [
            {
                "label": cls.tr("menu_components"),
                "icon": "icon_widget",
                "items": [
                    {"label": "DataTable", "key": "table"},
                    {
                        "label": cls.tr("menu_forms"),
                        "items": [
                            {"label": "InputText", "key": "input"},
                            {"label": "Select", "key": "select"},
                        ],
                    },
                    {"label": "Tree", "key": "tree"},
                ],
            },
            {
                "label": cls.tr("menu_pages"),
                "icon": "icon_home",
                "items": [
                    {"label": cls.tr("menu_dashboard"), "key": "dashboard"},
                    {"label": cls.tr("menu_settings"), "key": "settings"},
                ],
            },
            {"label": cls.tr("menu_disabled"), "disabled": True},
        ]

    @classmethod
    def _menubar_demo(cls) -> QWidget:
        bar = CMenubar(cls._items())
        return bar

    @classmethod
    def _tiered_demo(cls) -> QWidget:
        menu = CTieredMenu(cls._nested_items())
        return menu

    @classmethod
    def _mega_demo(cls) -> QWidget:
        menu = CMegaMenu(cls._items(), columns=2)
        menu.setFixedHeight(36)
        return menu

    @classmethod
    def _panel_demo(cls) -> QWidget:
        # CPanelMenu 自身按可见行数维护固定高度；不要再叠加外部最小高度，
        # 否则会形成 minHeight > maxHeight 的矛盾约束，展开内容被卡片裁切。
        return CPanelMenu(cls._nested_items())

    @classmethod
    def _context_demo(cls) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        menu = CContextMenu(cls._items())

        trigger = CButton(cls.tr("open_context"), icon="icon_menu", variant="outlined")
        trigger.clicked.connect(lambda: menu.show_at(trigger.mapToGlobal(trigger.rect().bottomLeft())))
        hint = QLabel(cls.tr("context_hint"))
        hint.setStyleSheet("color: palette(midlight);")
        layout.addWidget(trigger)
        layout.addWidget(hint, 1)
        return box

    @classmethod
    def _tab_menu_demo(cls) -> QWidget:
        return CTabMenu([cls.tr("tab_home"), cls.tr("tab_components"), cls.tr("tab_settings")])

    @classmethod
    def _stepper_demo(cls) -> QWidget:
        steps = []
        for index in range(1, 4):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 12, 0, 12)
            page_layout.addWidget(QLabel(cls.tr(f"step_{index}_body")))
            steps.append((cls.tr(f"step_{index}"), page))
        stepper = CStepper(steps)
        stepper.setMinimumHeight(220)
        return stepper

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_menubar"), cls._menubar_demo()),
            (cls.tr("group_tiered"), cls._tiered_demo()),
            (cls.tr("group_mega"), cls._mega_demo()),
            (cls.tr("group_panel"), cls._panel_demo()),
            (cls.tr("group_context"), cls._context_demo()),
            (cls.tr("group_tabmenu"), cls._tab_menu_demo()),
            (cls.tr("group_stepper"), cls._stepper_demo()),
        ]


PAGE = MenuPreviewPage
