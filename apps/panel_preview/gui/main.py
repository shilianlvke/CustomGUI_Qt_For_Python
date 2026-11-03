"""面板预览页：按 Sakai 的 Panel 族复刻标签页、手风琴、面板、字段集、工具栏、分割器、表单与导航。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from customgui.guicore import (
    CAccordion,
    CBreadcrumb,
    CButton,
    CFieldset,
    CFormGrid,
    CInputText,
    CPanel,
    CPreviewPage,
    CSplitter,
    CSteps,
    CTabs,
    CTextarea,
    CToolbar,
)


class PanelPreviewPage(CPreviewPage):
    """PAGE 协议入口：八类容器/布局组件。"""

    slug = "panel_preview"

    @classmethod
    def _toolbar_demo(cls) -> QWidget:
        bar = CToolbar()

        for icon in ("icon_add", "icon_search", "icon_trash"):
            button = CButton("", icon=icon, variant="outlined", severity="secondary")
            bar.add_start(button)

        bar.add_center(CInputText(placeholder=cls.tr("toolbar_search")))

        bar.add_end(CButton(cls.tr("toolbar_save"), icon="icon_check", severity="success"))
        return bar

    @staticmethod
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

    @classmethod
    def _tabs_demo(cls) -> QWidget:
        basic = CTabs()
        basic.add_tab(cls.tr("tab_header_1"), cls._tab_page(cls.tr("tab_content_1")), icon="icon_home")
        basic.add_tab(cls.tr("tab_header_2"), cls._tab_page(cls.tr("tab_content_2")))
        basic.add_tab(cls.tr("tab_header_3"), cls._tab_page(cls.tr("tab_content_3")))
        basic.add_tab(cls.tr("tab_disabled"), cls._tab_page(""), enabled=False)

        closable = CTabs(closable=True)
        closable.add_tab(cls.tr("tab_document"), cls._tab_page(cls.tr("tab_content_1")), icon="icon_bookmark")
        closable.add_tab(cls.tr("tab_image"), cls._tab_page(cls.tr("tab_content_2")), icon="icon_heart")
        closable.tabCloseRequested.connect(closable.remove_tab)

        bottom = CTabs(tab_position="bottom")
        bottom.add_tab(cls.tr("tab_header_1"), cls._tab_page(cls.tr("tab_content_1")))
        bottom.add_tab(cls.tr("tab_header_2"), cls._tab_page(cls.tr("tab_content_2")))

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(basic)
        layout.addWidget(closable)
        layout.addWidget(bottom)
        return box

    @classmethod
    def _accordion_demo(cls) -> QWidget:
        single = CAccordion()
        single.add_panel(
            cls.tr("accordion_header_1"),
            QLabel(cls.tr("accordion_body_1")),
            icon="icon_users",
            expanded=True,
        )
        single.add_panel(cls.tr("accordion_header_2"), QLabel(cls.tr("accordion_body_2")), icon="icon_setting")
        single.add_panel(cls.tr("accordion_header_3"), QLabel(cls.tr("accordion_body_3")), icon="icon_analysis")

        multiple = CAccordion(multiple=True)
        multiple.add_panel(cls.tr("accordion_header_1"), QLabel(cls.tr("accordion_body_1")), expanded=True)
        multiple.add_panel(cls.tr("accordion_header_2"), QLabel(cls.tr("accordion_body_2")), expanded=True)

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(single)
        layout.addWidget(multiple)
        return box

    @classmethod
    def _panel_demo(cls) -> QWidget:
        basic = CPanel(cls.tr("panel_title"), cls.tr("panel_subtitle"))
        basic.content_layout.addWidget(QLabel(cls.tr("panel_body")))

        toggle = CPanel(cls.tr("panel_toggle_title"), toggleable=True, collapsed=True)
        toggle.content_layout.addWidget(QLabel(cls.tr("panel_body")))

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(basic)
        layout.addWidget(toggle)
        return box

    @classmethod
    def _fieldset_demo(cls) -> QWidget:
        basic = CFieldset(cls.tr("fieldset_legend"))
        basic.content_layout.addWidget(QLabel(cls.tr("fieldset_body")))

        toggleable = CFieldset(cls.tr("fieldset_toggle_legend"), toggleable=True, collapsed=True)
        toggleable.content_layout.addWidget(QLabel(cls.tr("fieldset_body")))

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(basic)
        layout.addWidget(toggleable)
        return box

    @classmethod
    def _splitter_demo(cls) -> QWidget:
        def pane(text: str) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setAlignment(Qt.AlignCenter)
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return widget

        vertical = CSplitter("vertical")
        vertical.add_panel(pane(cls.tr("splitter_top")), size=50)
        vertical.add_panel(pane(cls.tr("splitter_bottom")), size=50)
        vertical.setMinimumHeight(200)

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(vertical)
        return box

    @classmethod
    def _form_demo(cls) -> QWidget:
        grid = CFormGrid(columns=2)
        grid.add_row(
            [
                (cls.tr("form_firstname"), CInputText(), "", True),
                (cls.tr("form_lastname"), CInputText()),
            ]
        )
        grid.add_field(cls.tr("form_bio"), CTextarea(), help_text=cls.tr("form_bio_help"))
        return grid

    @classmethod
    def _navigation_demo(cls) -> QWidget:
        steps = CSteps(
            [cls.tr("step_account"), cls.tr("step_personal"), cls.tr("step_payment"), cls.tr("step_confirm")],
            active=1,
        )

        breadcrumb = CBreadcrumb(
            [
                {"label": cls.tr("crumb_home")},
                {"label": cls.tr("crumb_components")},
                {"label": cls.tr("crumb_panels")},
            ]
        )

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(breadcrumb)
        layout.addWidget(steps)
        return box

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_toolbar"), cls._toolbar_demo()),
            (cls.tr("group_tabs"), cls._tabs_demo()),
            (cls.tr("group_accordion"), cls._accordion_demo()),
            (cls.tr("group_panel"), cls._panel_demo()),
            (cls.tr("group_fieldset"), cls._fieldset_demo()),
            (cls.tr("group_splitter"), cls._splitter_demo()),
            (cls.tr("group_form"), cls._form_demo()),
            (cls.tr("group_navigation"), cls._navigation_demo()),
        ]


PAGE = PanelPreviewPage
