"""面板预览页：按 Sakai 的 Panel 族复刻标签页、手风琴、面板、字段集、工具栏、分割器、表单与导航。

页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用，``self`` 是主窗口。
"""

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language
from GuiCore import (
    CAccordion,
    CBreadcrumb,
    CButton,
    CCard,
    CFieldset,
    CFormGrid,
    CInputText,
    CPanel,
    CScrollArea,
    CSplitter,
    CSteps,
    CTabs,
    CTextarea,
    CToolbar,
)

_LANG = "app.panel_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


# ----------------------------------------------------------------------
# 分组内容
# ----------------------------------------------------------------------
def _toolbar_demo() -> QWidget:
    bar = CToolbar()

    for icon in ("icon_add", "icon_search", "icon_trash"):
        button = CButton("", icon=icon, variant="outlined", severity="secondary")
        bar.add_start(button)

    bar.add_center(CInputText(placeholder=_t("toolbar_search")))

    bar.add_end(CButton(_t("toolbar_save"), icon="icon_check", severity="success"))
    return bar


def _tab_page(text: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 12, 0, 0)
    label = QLabel(text)
    label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    layout.addWidget(label)
    layout.addStretch()
    page.setMinimumHeight(110)
    return page


def _tabs_demo() -> QWidget:
    basic = CTabs()
    basic.add_tab(_t("tab_header_1"), _tab_page(_t("tab_content_1")), icon="icon_home")
    basic.add_tab(_t("tab_header_2"), _tab_page(_t("tab_content_2")))
    basic.add_tab(_t("tab_header_3"), _tab_page(_t("tab_content_3")))
    basic.add_tab(_t("tab_disabled"), _tab_page(""), enabled=False)

    closable = CTabs(closable=True)
    closable.add_tab(_t("tab_document"), _tab_page(_t("tab_content_1")), icon="icon_bookmark")
    closable.add_tab(_t("tab_image"), _tab_page(_t("tab_content_2")), icon="icon_heart")
    closable.tabCloseRequested.connect(closable.remove_tab)

    bottom = CTabs(tab_position="bottom")
    bottom.add_tab(_t("tab_header_1"), _tab_page(_t("tab_content_1")))
    bottom.add_tab(_t("tab_header_2"), _tab_page(_t("tab_content_2")))

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(basic)
    layout.addWidget(closable)
    layout.addWidget(bottom)
    return box


def _accordion_demo() -> QWidget:
    single = CAccordion()
    single.add_panel(
        _t("accordion_header_1"),
        QLabel(_t("accordion_body_1")),
        icon="icon_users",
        expanded=True,
    )
    single.add_panel(_t("accordion_header_2"), QLabel(_t("accordion_body_2")), icon="icon_setting")
    single.add_panel(_t("accordion_header_3"), QLabel(_t("accordion_body_3")), icon="icon_analysis")

    multiple = CAccordion(multiple=True)
    multiple.add_panel(_t("accordion_header_1"), QLabel(_t("accordion_body_1")), expanded=True)
    multiple.add_panel(_t("accordion_header_2"), QLabel(_t("accordion_body_2")), expanded=True)

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(single)
    layout.addWidget(multiple)
    return box


def _panel_demo() -> QWidget:
    basic = CPanel(_t("panel_title"), _t("panel_subtitle"))
    basic.content_layout.addWidget(QLabel(_t("panel_body")))

    toggle = CPanel(_t("panel_toggle_title"), toggleable=True, collapsed=True)
    toggle.content_layout.addWidget(QLabel(_t("panel_body")))

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(basic)
    layout.addWidget(toggle)
    return box


def _fieldset_demo() -> QWidget:
    basic = CFieldset(_t("fieldset_legend"))
    basic.content_layout.addWidget(QLabel(_t("fieldset_body")))

    toggleable = CFieldset(_t("fieldset_toggle_legend"), toggleable=True, collapsed=True)
    toggleable.content_layout.addWidget(QLabel(_t("fieldset_body")))

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(basic)
    layout.addWidget(toggleable)
    return box


def _splitter_demo() -> QWidget:
    def pane(text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        return widget

    vertical = CSplitter("vertical")
    vertical.add_panel(pane(_t("splitter_top")), size=50)
    vertical.add_panel(pane(_t("splitter_bottom")), size=50)
    vertical.setMinimumHeight(200)

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(vertical)
    return box


def _form_demo() -> QWidget:
    grid = CFormGrid(columns=2)
    grid.add_row(
        [
            (_t("form_firstname"), CInputText(), "", True),
            (_t("form_lastname"), CInputText()),
        ]
    )
    grid.add_field(_t("form_bio"), CTextarea(), help_text=_t("form_bio_help"))
    return grid


def _navigation_demo() -> QWidget:
    steps = CSteps(
        [_t("step_account"), _t("step_personal"), _t("step_payment"), _t("step_confirm")],
        active=1,
    )

    breadcrumb = CBreadcrumb(
        [
            {"label": _t("crumb_home")},
            {"label": _t("crumb_components")},
            {"label": _t("crumb_panels")},
        ]
    )

    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(breadcrumb)
    layout.addWidget(steps)
    return box


def _sections() -> list[tuple[str, QWidget]]:
    return [
        (_t("group_toolbar"), _toolbar_demo()),
        (_t("group_tabs"), _tabs_demo()),
        (_t("group_accordion"), _accordion_demo()),
        (_t("group_panel"), _panel_demo()),
        (_t("group_fieldset"), _fieldset_demo()),
        (_t("group_splitter"), _splitter_demo()),
        (_t("group_form"), _form_demo()),
        (_t("group_navigation"), _navigation_demo()),
    ]


# ----------------------------------------------------------------------
# 页面装配
# ----------------------------------------------------------------------
def _section_card(title: str, content: QWidget) -> CCard:
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


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("panelPreviewPage")
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

    for title, widget in _sections():
        content_layout.addWidget(_section_card(title, widget))
    content_layout.addStretch()
    return page


class PanelPreviewPage:
    """PAGE 协议入口：``load_page(window)`` 的 self 是主窗口。"""

    def load_page(self):
        _build_page(self)


PAGE = PanelPreviewPage
