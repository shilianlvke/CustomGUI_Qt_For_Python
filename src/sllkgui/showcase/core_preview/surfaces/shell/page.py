"""Sakai 壳层预览页：顶栏、嵌套侧边菜单与外观配置抽屉。"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.guicore import (
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

        # 设置不再以页面浮层出现：与标题栏、快捷键一致，打开独立设置窗口。
        trigger = CButton(cls.tr("open_config"), icon="icon_setting", variant="outlined")
        trigger.clicked.connect(lambda: cls._open_settings(window))

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
    def _open_settings(window) -> None:
        """打开独立设置窗口（与标题栏按钮、``Ctrl+,`` 走同一条路径）。"""
        controller = getattr(window, "controller", None)
        opener = getattr(controller, "open_settings_window", None)
        if callable(opener):
            opener()


def build(ctx):
    """Gallery Surface 工厂：注入插件上下文与翻译表。"""
    from ...common import bind_context

    bind_context(ctx)
    ShellPreviewPage._translator = lambda key, default=None: ctx.text(f"shell.{key}", default)
    page = ShellPreviewPage.build(ctx.parent_window())
    ctx.event("surface.ready", {"surface": "shell"})
    return page
