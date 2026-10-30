"""浮层预览页：按 Sakai 的 Overlay 页复刻对话框、抽屉、确认框与浮层面板。

页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用，``self`` 是主窗口。
"""

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language
from GuiCore import (
    CButton,
    CCard,
    CConfirmDialog,
    CDialog,
    CDivider,
    CDrawer,
    COverlayPanel,
    CScrollArea,
    CToast,
)

_LANG = "app.overlay_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _toast_offset(window) -> int:
    bar = getattr(getattr(window, "ui", None), "title_bar", None)
    return bar.height() + 8 if bar is not None else 56


def _toast(window, text: str, severity: str = "info", title: str = "") -> None:
    CToast.show_message(window, text, title, severity, offset_top=_toast_offset(window))


# ----------------------------------------------------------------------
# 分组内容
# ----------------------------------------------------------------------
def _show_dialog(window, header: bool, width: int) -> None:
    dialog = CDialog(
        title=_t("dialog_title") if header else "",
        text=_t("dialog_text"),
        width=width,
        accept_text=_t("dialog_accept"),
        reject_text=_t("dialog_cancel"),
        closable=header,
        parent=window,
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.accepted.connect(lambda: _toast(window, _t("toast_saved"), "success"))
    dialog.open_dialog()


def _dialog_buttons(window):
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    basic = CButton(_t("dialog_basic"))
    basic.clicked.connect(lambda: _show_dialog(window, True, 480))
    no_header = CButton(_t("dialog_no_header"), variant="outlined", severity="secondary")
    no_header.clicked.connect(lambda: _show_dialog(window, False, 420))
    large = CButton(_t("dialog_large"), variant="outlined", severity="secondary")
    large.clicked.connect(lambda: _show_dialog(window, True, 640))
    for button in (basic, no_header, large):
        layout.addWidget(button)
    layout.addStretch()
    return [box]


def _show_drawer(window, position: str) -> None:
    size = 380 if position in ("left", "right") else 260
    drawer = CDrawer(_t("drawer_title"), position=position, size=size, parent=window)
    drawer.setAttribute(Qt.WA_DeleteOnClose, True)

    text = QLabel(_t("drawer_body"))
    text.setWordWrap(True)
    drawer.content_layout.addWidget(text)
    close = CButton(_t("dialog_cancel"), variant="outlined", severity="secondary")
    close.clicked.connect(drawer.reject)
    drawer.content_layout.addWidget(close)
    drawer.open_dialog()


def _drawer_buttons(window):
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for position in ("left", "right", "top", "bottom"):
        button = CButton(_t(f"drawer_{position}"), variant="outlined", severity="secondary")
        button.clicked.connect(lambda _checked=False, p=position: _show_drawer(window, p))
        layout.addWidget(button)
    layout.addStretch()
    return [box]


def _show_confirm(window, severity: str) -> None:
    dialog = CConfirmDialog(
        _t("confirm_title"),
        _t("confirm_message"),
        severity,
        _t("confirm_accept"),
        _t("confirm_reject"),
        parent=window,
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.accepted.connect(lambda: _toast(window, _t("toast_confirmed"), "success"))
    dialog.rejected.connect(lambda: _toast(window, _t("toast_cancelled"), "info"))
    dialog.open_dialog()


def _confirm_buttons(window):
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for severity in ("info", "success", "warn", "error"):
        button = CButton(_t(f"confirm_{severity}"), severity=severity)
        button.clicked.connect(lambda _checked=False, s=severity: _show_confirm(window, s))
        layout.addWidget(button)
    layout.addStretch()
    return [box]


def _panel_buttons(window):
    button = CButton(_t("panel_show"))
    panel = COverlayPanel(button, width=280)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    title = QLabel(_t("panel_title"))
    font = QFont(AppSettings.family, 13)
    font.setWeight(QFont.Weight.DemiBold)
    title.setFont(font)
    layout.addWidget(title)
    layout.addWidget(CDivider())
    action = CButton(_t("panel_action"), variant="text", severity="danger")
    action.clicked.connect(panel.close_panel)
    layout.addWidget(action)
    panel.set_content(content)

    button.clicked.connect(panel.toggle)
    return [button]


def _sections(window):
    return [
        (_t("group_dialog"), _dialog_buttons(window), 1),
        (_t("group_drawer"), _drawer_buttons(window), 1),
        (_t("group_confirm"), _confirm_buttons(window), 1),
        (_t("group_panel"), _panel_buttons(window), 1),
    ]


# ----------------------------------------------------------------------
# 页面装配
# ----------------------------------------------------------------------
def _section_card(title: str, widgets, columns: int = 1) -> CCard:
    card = CCard()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(QMargins(12, 10, 12, 12))
    layout.setSpacing(8)

    label = QLabel(title)
    font = QFont(AppSettings.family, AppSettings.subtitle_size)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    layout.addWidget(label)

    for start in range(0, len(widgets), columns):
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in widgets[start : start + columns]:
            row.addWidget(widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
        row.addStretch()
        layout.addLayout(row)
    return card


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("overlayPreviewPage")
    window.ui.load_pages.pages.addWidget(page)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(QMargins(0, 0, 0, 0))
    outer.setSpacing(0)

    scroller = CScrollArea()
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(QMargins(6, 6, 6, 6))
    content_layout.setSpacing(6)
    scroller.setWidget(content)
    scroller.setWidgetResizable(True)
    outer.addWidget(scroller)

    for title, widgets, columns in _sections(window):
        content_layout.addWidget(_section_card(title, widgets, columns))
    content_layout.addStretch()
    return page


class OverlayPreviewPage:
    """PAGE 协议入口：``load_page(window)`` 的 self 是主窗口。"""

    def load_page(self):
        _build_page(self)


PAGE = OverlayPreviewPage
