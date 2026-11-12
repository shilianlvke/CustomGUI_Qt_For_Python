"""输入预览页：按 Sakai 输入页展示全部表单控件。

分组对应 https://sakai.primevue.org/uikit/input 的 18 个区块，卡片划分也与参考页一致
（参考页是 6 张卡片，一张卡片里放多个小标题，而不是每个控件一张卡）：
InputText / Icons / Float Label / Textarea / AutoComplete / DatePicker / InputNumber ｜
Slider / Rating / ColorPicker / Knob ｜ RadioButton / Checkbox / ToggleSwitch ｜
Listbox / Select / MultiSelect / TreeSelect ｜ ToggleButton / SelectButton ｜ InputGroup。
"""

from PySide6.QtCore import QDate, QMargins, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.appcore import ColorPalette
from sllkgui.guicore import (
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
    CPreviewPage,
    CRadioButton,
    CRating,
    CSelect,
    CSelectButton,
    CSlider,
    CTextarea,
    CToggleButton,
    CToggleSwitch,
    CTreeSelect,
)

from ...common import log

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


class InputPreviewPage(CPreviewPage):
    """PAGE 协议入口：表单控件按参考页的六张卡片划分。

    与其它预览页不同，这里的卡片内部还有一层「小标题 + 控件组」结构，
    因此覆写了 :meth:`card_for`，由 :meth:`block` 渲染卡片内的子块。
    """

    slug = "input_preview"
    title_scale = "title"

    # ------------------------------------------------------------------
    # 分组内容
    # ------------------------------------------------------------------
    @classmethod
    def _input_text_buttons(cls):
        disabled = CInputText(placeholder="Disabled")
        disabled.setEnabled(False)
        invalid = CInputText(placeholder="Invalid")
        invalid.set_invalid(True)
        invalid.textChanged.connect(lambda text: log(f"非法态输入: {text}"))
        return [
            cls.fixed(CInputText(placeholder="Default"), 220),
            cls.fixed(disabled, 220),
            cls.fixed(invalid, 220),
        ]

    @classmethod
    def _icon_inputs(cls):
        return [
            cls.fixed(CInputText(placeholder="Username", icon="icon_users", icon_pos="left"), 240),
            cls.fixed(CInputText(placeholder="Search", icon="icon_search", icon_pos="right"), 240),
        ]

    @classmethod
    def _float_labels(cls):
        username = CFloatLabel("Username")
        email = CFloatLabel("Email")
        email.setText("user@example.com")
        return [cls.fixed(username, 240), cls.fixed(email, 240)]

    @classmethod
    def _textareas(cls):
        return [cls.fixed(CTextarea(placeholder="Your Message", rows=3), 420)]

    @classmethod
    def _input_numbers(cls):
        return [
            cls.fixed(CInputNumber(value=42, minimum=0, maximum=999, step=5, placeholder="Price"), 190),
            cls.fixed(CInputNumber(value=8.5, minimum=0, maximum=100, step=0.5, decimals=1, placeholder="Quantity"), 190),
        ]

    @classmethod
    def _autocompletes(cls):
        return [
            cls.fixed(
                CAutoComplete(_FRAMEWORKS, ["React"], placeholder="Search"),
                240,
            )
        ]

    @classmethod
    def _date_pickers(cls):
        return [cls.fixed(CDatePicker(QDate.currentDate()), 240)]

    @classmethod
    def _sliders(cls):
        field = cls.fixed(CInputText(text="50"), 90)
        slider = cls.fixed(CSlider(50), 240)
        slider.valueChanged.connect(lambda value: field.setText(str(value)))
        field.textChanged.connect(lambda text: slider.setValue(int(text)) if text.strip().isdigit() else None)
        return [field, slider]

    @staticmethod
    def _ratings():
        return [CRating(3)]

    @staticmethod
    def _color_pickers():
        return [CColorPicker(ColorPalette.custom_green)]

    @staticmethod
    def _knobs():
        return [CKnob(20, -50, 50, 10, value_template="{value}%")]

    @staticmethod
    def _radio_buttons():
        buttons = [CRadioButton(city, checked=index == 0) for index, city in enumerate(_CITIES)]
        for button in buttons:
            # 在 lambda 之前取值：默认参数里调用 button.text() 会在定义时求值，
            # 既触发 B008，也让后续按钮文本变化无法反映到回调。
            name = button.text()
            button.toggled.connect(lambda checked, name=name: checked and log(f"单选: {name}"))
        return buttons

    @staticmethod
    def _checkboxes():
        return [CCheckbox(city, checked=index == 0) for index, city in enumerate(_CITIES)]

    @staticmethod
    def _toggle_switches():
        return [CToggleSwitch(checked=True)]

    @classmethod
    def _listboxes(cls):
        return [cls.fixed(CListbox(_OPTIONS, "Rome", height=232), 420)]

    @classmethod
    def _selects(cls):
        return [cls.fixed(CSelect(_OPTIONS, "Rome", placeholder="Select", filter=True), 240)]

    @classmethod
    def _multi_selects(cls):
        return [
            cls.fixed(
                CMultiSelect(_FRAMEWORKS, ["React", "Vue"], placeholder="Select", filter=True),
                260,
            )
        ]

    @classmethod
    def _tree_selects(cls):
        return [cls.fixed(CTreeSelect(_TREE, placeholder="Select Item"), 240)]

    @classmethod
    def _toggle_buttons(cls):
        return [cls.fixed(CToggleButton("Yes", "No", checked=False), 160)]

    @staticmethod
    def _select_buttons():
        return [CSelectButton(["Off", "On"], 0)]

    @classmethod
    def _input_groups(cls):
        return [
            cls.fixed(CInputGroup([CInputGroupAddon(icon="icon_users"), CInputText(placeholder="Username")]), 330),
            cls.fixed(
                CInputGroup(
                    [
                        CInputGroupAddon(icon="icon_heart"),
                        CInputNumber(value=10, minimum=0, maximum=100, show_buttons=False),
                        CInputGroupAddon(text="$"),
                        CInputGroupAddon(text=".00"),
                    ]
                ),
                330,
            ),
            cls.fixed(CInputGroup([CButton(text="Search"), CInputText(placeholder="Keyword")]), 330),
            cls.fixed(CInputGroup([CInputGroupAddon(widget=CCheckbox()), CInputText(placeholder="Confirm")]), 330),
        ]

    @classmethod
    def _bodies(cls):
        """按参考页的卡片划分返回页面结构。

        每张卡片是一组「子块」；子块为 ``(标题, 控件列表, 每行列数)``，若某一项是列表
        则表示这几个子块并排（对应 Sakai 的 ``flex-row``，例如 Rating 与 ColorPicker）。
        """
        return [
            [
                (cls.tr("group_inputtext"), cls._input_text_buttons(), 3),
                (cls.tr("group_icons"), cls._icon_inputs(), 2),
                (cls.tr("group_floatlabel"), cls._float_labels(), 2),
                (cls.tr("group_textarea"), cls._textareas(), 1),
                (cls.tr("group_autocomplete"), cls._autocompletes(), 1),
                (cls.tr("group_datepicker"), cls._date_pickers(), 1),
                (cls.tr("group_inputnumber"), cls._input_numbers(), 2),
            ],
            [
                (cls.tr("group_slider"), cls._sliders(), 1),
                [(cls.tr("group_rating"), cls._ratings(), 1), (cls.tr("group_colorpicker"), cls._color_pickers(), 1)],
                (cls.tr("group_knob"), cls._knobs(), 1),
            ],
            [
                (cls.tr("group_radio"), cls._radio_buttons(), 3),
                (cls.tr("group_checkbox"), cls._checkboxes(), 3),
                (cls.tr("group_toggleswitch"), cls._toggle_switches(), 1),
            ],
            [
                (cls.tr("group_listbox"), cls._listboxes(), 1),
                (cls.tr("group_select"), cls._selects(), 1),
                (cls.tr("group_multiselect"), cls._multi_selects(), 1),
                (cls.tr("group_treeselect"), cls._tree_selects(), 1),
            ],
            [
                (cls.tr("group_togglebutton"), cls._toggle_buttons(), 1),
                (cls.tr("group_selectbutton"), cls._select_buttons(), 1),
            ],
            [
                (cls.tr("group_inputgroup"), cls._input_groups(), 2),
            ],
        ]

    # ------------------------------------------------------------------
    # 卡片装配
    # ------------------------------------------------------------------
    @classmethod
    def block(cls, title: str, widgets, columns: int = 3) -> QWidget:
        """卡片里的一个小标题 + 若干行控件。"""
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(QMargins(0, 0, 0, 0))
        layout.setSpacing(8)
        layout.addWidget(cls.title_label(title))

        step = max(1, int(columns))
        for start in range(0, len(widgets), step):
            row = QHBoxLayout()
            row.setSpacing(8)
            for widget in widgets[start : start + step]:
                row.addWidget(widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
            row.addStretch()
            layout.addLayout(row)
        return block

    @classmethod
    def card_for(cls, item, page, window) -> QWidget:
        """一张卡片：子块自上而下排列，列表项表示并排的子块。"""
        card = CCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(QMargins(12, 10, 12, 14))
        layout.setSpacing(14)

        for entry in item:
            if isinstance(entry, list):
                row = QHBoxLayout()
                row.setSpacing(24)
                for title, widgets, columns in entry:
                    row.addWidget(cls.block(title, widgets, columns), 1)
                layout.addLayout(row)
            else:
                title, widgets, columns = entry
                layout.addWidget(cls.block(title, widgets, columns))
        return card

    @classmethod
    def sections(cls, page, window):
        return cls._bodies()


def build(ctx):
    """Gallery Surface 工厂：注入插件上下文与翻译表。"""
    from ...common import bind_context

    bind_context(ctx)
    InputPreviewPage._translator = lambda key, default=None: ctx.text(f"inputs.{key}", default)
    page = InputPreviewPage.build(ctx.parent_window())
    ctx.event("surface.ready", {"surface": "inputs"})
    return page
