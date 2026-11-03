"""Sakai 壳层预览页：顶栏、嵌套侧边菜单与主题配置抽屉。"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.guicore import (
    CAppConfigurator,
    CAppMenu,
    CAppTopbar,
    CButton,
    CPreviewPage,
)


class ShellPreviewPage(CPreviewPage):
    """PAGE 协议入口：壳层三件套（顶栏 / 菜单 / 主题抽屉）。"""

    slug = "shell_preview"

    @classmethod
    def _menu_items(cls) -> list[dict]:
        return [
            {
                "label": cls.tr("group_ui"),
                "icon": "icon_widget",
                "items": [
                    {"label": "DataTable", "key": "table"},
                    {"label": "List", "key": "list"},
                    {
                        "label": cls.tr("group_forms"),
                        "items": [
                            {"label": "InputText", "key": "input"},
                            {"label": "Select", "key": "select"},
                        ],
                    },
                ],
            },
            {
                "label": cls.tr("group_pages"),
                "icon": "icon_home",
                "items": [
                    {"label": cls.tr("menu_dashboard"), "key": "dashboard"},
                    {"label": cls.tr("menu_settings"), "key": "settings"},
                ],
            },
        ]

    @classmethod
    def sections(cls, page, window):
        # 状态条串起顶栏、菜单与配置抽屉的反馈，所有回调都写到这里
        status = QLabel(cls.tr("hint"))
        status.setStyleSheet("color: palette(mid);")

        topbar = CAppTopbar(title="Sakai Shell", logo="mihoutao")
        topbar.set_user("Y")
        topbar.set_unread_count(3)
        topbar.searchChanged.connect(lambda text: status.setText(f"{cls.tr('search')}: {text}"))
        topbar.notificationsClicked.connect(lambda: status.setText(cls.tr("notifications")))
        topbar.userMenuRequested.connect(lambda: status.setText(cls.tr("user_menu")))

        menu = CAppMenu(cls._menu_items())
        menu.setMinimumWidth(280)
        menu.itemClicked.connect(lambda item: status.setText(f"{cls.tr('menu_selected')}: {getattr(item, 'label', item)}"))

        # 抽屉以页面为父对象挂在页面上，页面存一份引用便于外部访问
        configurator = CAppConfigurator(page)
        configurator.setVisible(False)
        configurator.themeChanged.connect(lambda name: status.setText(f"{cls.tr('theme')}: {name}"))
        page._shell_configurator = configurator

        trigger = CButton(cls.tr("open_config"), icon="icon_config", variant="outlined")
        trigger.clicked.connect(configurator.toggle)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(cls.card(cls.tr("group_menu"), menu), 2)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        right.addWidget(cls.card(cls.tr("group_config"), trigger))
        right.addWidget(status)
        right.addStretch(1)
        row_layout.addLayout(right, 3)

        return [cls.card(cls.tr("group_topbar"), topbar), row]


PAGE = ShellPreviewPage
