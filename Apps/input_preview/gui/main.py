"""输入预览页：按 Sakai 输入页展示全部表单控件。

分组对应 https://sakai.primevue.org/uikit/input 的 21 个区块：
InputText / Sizes / Icons / Float Label / Textarea / AutoComplete / DatePicker /
InputNumber / Slider / Rating / ColorPicker / Knob / RadioButton / Checkbox /
ToggleSwitch / Listbox / Select / MultiSelect / TreeSelect / ToggleButton /
SelectButton / InputGroup。

页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用，因此 ``self`` 是主窗口，
全部构建逻辑放在模块级函数里。
"""

from PySide6.QtCore import QDate, QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language, Logger
from GuiCore import (
    CAutoComplete,
    CButton,
    CCard,
    CCheckbox,
    CColorPicker,
    CDatePicker,
    CFloatLabel,
    CInputGroup,
    CInputGroupAddon,
    CInputNumber,
    CInputText,
    CKnob,
    CListbox,
    CMultiSelect,
    CRadioButton,
    CRating,
    CScrollArea,
    CSelect,
    CSelectButton,
    CSlider,
    CTextarea,
    CToggleButton,
    CToggleSwitch,
    CTreeSelect,
)

_LANG = "app.input_preview"

_CITIES = ("Chicago", "Los Angeles", "New York")
_OPTIONS = ("Rome", "London", "Paris", "Berlin", "Madrid")
_FRAMEWORKS = ("React", "Vue", "Angular", "Svelte", "Solid")
_TREE = (
    {
        "label": "Documents",
        "children": (
            {"label": "Work", "children": ({"label": "Expenses.doc"}, {"label": "Resume.doc"})},
            {"label": "Home", "children": ({"label": "Invoices.txt"},)},
        ),
    },
    {"label": "Pictures", "children": ({"label": "barcelona.jpg"}, {"label": "logo.png"})},
    {"label": "Movies"},
)


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
    return [
        _fixed(CInputNumber(value=42, minimum=0, maximum=999, step=5, placeholder="Price"), 190),
        _fixed(CInputNumber(value=8.5, minimum=0, maximum=100, step=0.5, decimals=1, placeholder="Quantity"), 190),
    ]


def _autocompletes():
    return [
        _fixed(
            CAutoComplete(_FRAMEWORKS, ["React"], placeholder="Search"),
            240,
        )
    ]


def _date_pickers():
    return [_fixed(CDatePicker(QDate.currentDate()), 240)]


def _sliders():
    field = _fixed(CInputText(text="50"), 90)
    slider = _fixed(CSlider(50), 240)
    slider.valueChanged.connect(lambda value: field.setText(str(value)))
    field.textChanged.connect(lambda text: slider.setValue(int(text)) if text.strip().isdigit() else None)
    return [field, slider]


def _ratings():
    return [CRating(3)]


def _color_pickers():
    return [CColorPicker("#22c55e")]


def _knobs():
    return [CKnob(20, -50, 50, 10)]


def _radio_buttons():
    buttons = [CRadioButton(city, checked=index == 0) for index, city in enumerate(_CITIES)]
    for button in buttons:
        button.toggled.connect(lambda checked, name=button.text(): checked and Logger.info(f"单选: {name}"))
    return buttons


def _checkboxes():
    return [CCheckbox(city, checked=index == 0) for index, city in enumerate(_CITIES)]


def _toggle_switches():
    return [CToggleSwitch("Wifi", checked=True)]


def _listboxes():
    return [_fixed(CListbox(_OPTIONS, "Rome", height=232), 420)]


def _selects():
    return [_fixed(CSelect(_OPTIONS, "Rome", placeholder="Select", filter=True), 240)]


def _multi_selects():
    return [
        _fixed(
            CMultiSelect(_FRAMEWORKS, ["React", "Vue"], placeholder="Select", filter=True),
            260,
        )
    ]


def _tree_selects():
    return [_fixed(CTreeSelect(_TREE, placeholder="Select Item"), 240)]


def _toggle_buttons():
    return [CToggleButton("Yes", "No", checked=False)]


def _select_buttons():
    return [CSelectButton(["Off", "On"], 0)]


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
        _fixed(CInputGroup([CInputGroupAddon(widget=CCheckbox()), CInputText(placeholder="Confirm")]), 420),
    ]


def _sections():
    return [
        (_t("group_inputtext"), _input_text_buttons(), 3),
        (_t("group_sizes"), _size_inputs(), 3),
        (_t("group_icons"), _icon_inputs(), 2),
        (_t("group_floatlabel"), _float_labels(), 2),
        (_t("group_textarea"), _textareas(), 1),
        (_t("group_autocomplete"), _autocompletes(), 2),
        (_t("group_datepicker"), _date_pickers(), 2),
        (_t("group_inputnumber"), _input_numbers(), 2),
        (_t("group_slider"), _sliders(), 2),
        (_t("group_rating"), _ratings(), 1),
        (_t("group_colorpicker"), _color_pickers(), 1),
        (_t("group_knob"), _knobs(), 1),
        (_t("group_radio"), _radio_buttons(), 3),
        (_t("group_checkbox"), _checkboxes(), 3),
        (_t("group_toggleswitch"), _toggle_switches(), 1),
        (_t("group_listbox"), _listboxes(), 1),
        (_t("group_select"), _selects(), 2),
        (_t("group_multiselect"), _multi_selects(), 2),
        (_t("group_treeselect"), _tree_selects(), 2),
        (_t("group_togglebutton"), _toggle_buttons(), 1),
        (_t("group_selectbutton"), _select_buttons(), 1),
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
