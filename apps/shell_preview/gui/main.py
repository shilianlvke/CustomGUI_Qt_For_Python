"""Sakai 壳层预览页：顶栏、嵌套侧边菜单与外观配置抽屉。"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from customgui.guicore import (
    CAppMenu,
    CAppTopbar,
    CButton,
    CPreviewPage,
)


class ShellPreviewPage(CPreviewPage):
    """PAGE 协议入口：壳层三件套（顶栏 / 菜单 / 外观配置）。"""

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
        topbar = CAppTopbar(title="Sakai Shell", logo="mihoutao")
        topbar.set_user("Y")
        topbar.set_unread_count(3)

        menu = CAppMenu(cls._menu_items())
        menu.setMinimumWidth(280)

        # 外观配置不再以页面浮层出现：改为打开主窗口右侧抽屉里的配置页。
        trigger = CButton(cls.tr("open_config"), icon="icon_palette", variant="outlined")
        trigger.clicked.connect(lambda: cls._toggle_theme_drawer(window))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(cls.card(cls.tr("group_menu"), menu), 2)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        right.addWidget(cls.card(cls.tr("group_config"), trigger))
        right.addStretch(1)
        row_layout.addLayout(right, 3)

        return [cls.card(cls.tr("group_topbar"), topbar), row]

    @staticmethod
    def _toggle_theme_drawer(window) -> None:
        """打开/收起主窗口右侧的外观配置抽屉（兼容无 controller 的测试宿主）。"""
        controller = getattr(window, "controller", None)
        theme_controller = getattr(controller, "theme_controller", None) if controller is not None else None
        toggle = getattr(theme_controller, "toggle_theme_drawer", None)
        if callable(toggle):
            toggle()
            return

        ui = getattr(window, "ui", None)
        menu = getattr(ui, "theme_menu", None)
        if menu is None or not hasattr(ui, "right_column"):
            return
        from customgui.guis.windows.main_window.functions import MainFunctions

        ui.right_column.menus.setCurrentWidget(menu)
        if not MainFunctions.right_column_is_visible(window):
            MainFunctions.toggle_right_column(window)


PAGE = ShellPreviewPage
