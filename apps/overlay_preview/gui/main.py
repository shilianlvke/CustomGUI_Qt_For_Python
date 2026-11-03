"""浮层预览页：按 Sakai 的 Overlay 页复刻对话框、抽屉、确认框与浮层面板。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings
from customgui.guicore import (
    CButton,
    CConfirmDialog,
    CDialog,
    CDivider,
    COverlayPanel,
    CPreviewPage,
    CToast,
)


class OverlayPreviewPage(CPreviewPage):
    """PAGE 协议入口：四类浮层各占一张卡片。"""

    slug = "overlay_preview"
    columns = 1

    # ------------------------------------------------------------------
    # 浮层工具
    # ------------------------------------------------------------------
    @staticmethod
    def _offset_top(window) -> int:
        bar = getattr(getattr(window, "ui", None), "title_bar", None)
        return bar.height() + 8 if bar is not None else 56

    @classmethod
    def _toast(cls, window, text: str, severity: str = "info", title: str = "") -> None:
        CToast.show_message(window, text, title, severity, offset_top=cls._offset_top(window))

    @classmethod
    def _show_dialog(cls, window, header: bool, width: int) -> None:
        dialog = CDialog(
            title=cls.tr("dialog_title") if header else "",
            text=cls.tr("dialog_text"),
            width=width,
            accept_text=cls.tr("dialog_accept"),
            reject_text=cls.tr("dialog_cancel"),
            closable=header,
            parent=window,
        )
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.accepted.connect(lambda: cls._toast(window, cls.tr("toast_saved"), "success"))
        dialog.open_dialog()

    # ------------------------------------------------------------------
    # 分组内容
    # ------------------------------------------------------------------
    @classmethod
    def _dialog_buttons(cls, window):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        basic = CButton(cls.tr("dialog_basic"))
        basic.clicked.connect(lambda: cls._show_dialog(window, True, 480))
        no_header = CButton(cls.tr("dialog_no_header"), variant="outlined", severity="secondary")
        no_header.clicked.connect(lambda: cls._show_dialog(window, False, 420))
        large = CButton(cls.tr("dialog_large"), variant="outlined", severity="secondary")
        large.clicked.connect(lambda: cls._show_dialog(window, True, 640))
        for button in (basic, no_header, large):
            layout.addWidget(button)
        layout.addStretch()
        return [box]

    @classmethod
    def _toggle_column(cls, window, position: str) -> None:
        """切换指定方向的栏目抽屉（左/右列为基座既有栏目，顶/底列与之同构）。"""
        from customgui.appcore import PathFactory
        from customgui.guis.windows.main_window.functions import MainFunctions

        if position == "left":
            MainFunctions.set_left_column_menu(
                window,
                menu=window.ui.left_column.menus.menu_2,
                title=cls.tr("drawer_left_title"),
                icon_path=PathFactory.set_svg_icon("icon_setting"),
            )
            MainFunctions.toggle_left_column(window)
        elif position == "right":
            MainFunctions.toggle_right_column(window)
        elif position == "top":
            MainFunctions.set_top_column_menu(
                window,
                menu=window.ui.top_column.menus.menu_1,
                title=cls.tr("drawer_top_title"),
                icon_path=PathFactory.set_svg_icon("icon_search"),
            )
            MainFunctions.toggle_top_column(window)
        else:
            MainFunctions.set_bottom_column_menu(
                window,
                menu=window.ui.bottom_column.menus.menu_1,
                title=cls.tr("drawer_bottom_title"),
                icon_path=PathFactory.set_svg_icon("icon_report"),
            )
            MainFunctions.toggle_bottom_column(window)

    @classmethod
    def _drawer_buttons(cls, window):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for position in ("left", "right", "top", "bottom"):
            button = CButton(cls.tr(f"drawer_{position}"), variant="outlined", severity="secondary")
            button.clicked.connect(lambda _checked=False, p=position: cls._toggle_column(window, p))
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

        note = QLabel(cls.tr("drawer_note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        return [box]

    @classmethod
    def _show_confirm(cls, window, severity: str) -> None:
        dialog = CConfirmDialog(
            cls.tr("confirm_title"),
            cls.tr("confirm_message"),
            severity,
            cls.tr("confirm_accept"),
            cls.tr("confirm_reject"),
            parent=window,
        )
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.accepted.connect(lambda: cls._toast(window, cls.tr("toast_confirmed"), "success"))
        dialog.rejected.connect(lambda: cls._toast(window, cls.tr("toast_cancelled"), "info"))
        dialog.open_dialog()

    @classmethod
    def _confirm_buttons(cls, window):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for severity in ("info", "success", "warn", "error"):
            button = CButton(cls.tr(f"confirm_{severity}"), severity=severity)
            button.clicked.connect(lambda _checked=False, s=severity: cls._show_confirm(window, s))
            layout.addWidget(button)
        layout.addStretch()
        return [box]

    @classmethod
    def _panel_buttons(cls, window):
        button = CButton(cls.tr("panel_show"))
        panel = COverlayPanel(button, width=280)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel(cls.tr("panel_title"))
        font = QFont(AppSettings.family, 13)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)
        layout.addWidget(title)
        layout.addWidget(CDivider())
        action = CButton(cls.tr("panel_action"), variant="text", severity="danger")
        action.clicked.connect(panel.close_panel)
        layout.addWidget(action)
        panel.set_content(content)

        button.clicked.connect(panel.toggle)
        return [button]

    # ------------------------------------------------------------------
    # 页面结构
    # ------------------------------------------------------------------
    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_dialog"), cls._dialog_buttons(window), 1),
            (cls.tr("group_drawer"), cls._drawer_buttons(window), 1),
            (cls.tr("group_confirm"), cls._confirm_buttons(window), 1),
            (cls.tr("group_panel"), cls._panel_buttons(window), 1),
        ]


PAGE = OverlayPreviewPage
