"""输入预览页：按 Sakai 输入页（批次 1）展示输入组件。

分组对应 https://sakai.primevue.org/uikit/input 的文本输入部分：
InputText / Sizes / Icons / Float Label / Textarea / InputNumber / InputGroup。
批次 2–4（开关、选择器、数值可视化）见 line_edit/README.md。

页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用，因此 ``self`` 是主窗口，
全部构建逻辑放在模块级函数里。
"""

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language, Logger
from GuiCore import (
    CButton,
    CCard,
    CFloatLabel,
    CInputGroup,
    CInputGroupAddon,
    CInputNumber,
    CInputText,
    CScrollArea,
    CTextarea,
)

_LANG = "app.input_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


# ----------------------------------------------------------------------
# 分组内容
# ----------------------------------------------------------------------
def _fixed(widget, width: int):
    """预览页里给控件一个稳定的演示宽度（否则 fluid 输入框会铺满整行）。"""
    widget.setFixedWidth(width)
    return widget


def _input_text_buttons():
    disabled = CInputText(placeholder="Disabled")
    disabled.setEnabled(False)
    invalid = CInputText(placeholder="Invalid")
    invalid.set_invalid(True)
    invalid.textChanged.connect(lambda text: Logger.info(f"非法态输入: {text}"))
    return [
        _fixed(CInputText(placeholder="Default"), 220),
        _fixed(disabled, 220),
        _fixed(invalid, 220),
    ]


def _size_inputs():
    return [
        _fixed(CInputText(placeholder="Small", size="sm"), 170),
        _fixed(CInputText(placeholder="Default", size="md"), 210),
        _fixed(CInputText(placeholder="Large", size="lg"), 250),
    ]


def _icon_inputs():
    return [
        _fixed(CInputText(placeholder="Username", icon="icon_users", icon_pos="left"), 240),
        _fixed(CInputText(placeholder="Search", icon="icon_search", icon_pos="right"), 240),
    ]


def _float_labels():
    username = CFloatLabel("Username")
    email = CFloatLabel("Email")
    email.setText("user@example.com")
    return [_fixed(username, 240), _fixed(email, 240)]


def _textareas():
    return [_fixed(CTextarea(placeholder="Your Message", rows=3), 420)]


def _input_numbers():
    return [_fixed(CInputNumber(value=42, minimum=0, maximum=999, step=5, placeholder="Price"), 200)]


def _input_groups():
    return [
        _fixed(CInputGroup([CInputGroupAddon(icon="icon_users"), CInputText(placeholder="Username")]), 420),
        _fixed(
            CInputGroup(
                [
                    CInputGroupAddon(icon="icon_heart"),
                    CInputNumber(value=10, minimum=0, maximum=100, show_buttons=False),
                    CInputGroupAddon(text="$"),
                    CInputGroupAddon(text=".00"),
                ]
            ),
            420,
        ),
        _fixed(CInputGroup([CButton(text="Search"), CInputText(placeholder="Keyword")]), 420),
    ]


def _sections():
    return [
        (_t("group_inputtext"), _input_text_buttons(), 3),
        (_t("group_sizes"), _size_inputs(), 3),
        (_t("group_icons"), _icon_inputs(), 2),
        (_t("group_floatlabel"), _float_labels(), 2),
        (_t("group_textarea"), _textareas(), 1),
        (_t("group_inputnumber"), _input_numbers(), 2),
        (_t("group_inputgroup"), _input_groups(), 1),
    ]


# ----------------------------------------------------------------------
# 页面装配
# ----------------------------------------------------------------------
def _section_card(title: str, widgets, columns: int = 3) -> CCard:
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
    page.setObjectName("inputPreviewPage")
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

    for title, widgets, columns in _sections():
        content_layout.addWidget(_section_card(title, widgets, columns))
    content_layout.addStretch()
    return page


class InputPreviewPage:
    """PAGE 协议入口：``load_page(window)`` 的 self 是主窗口。"""

    def load_page(self):
        _build_page(self)


PAGE = InputPreviewPage
