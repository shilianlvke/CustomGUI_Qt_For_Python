# 输入组件复刻计划（Sakai / PrimeVue Aura）

复刻对象：<https://sakai.primevue.org/uikit/input>
源码依据：`sakai-vue/src/views/uikit/InputDoc.vue` + `@primeuix/themes` 的 `presets/aura/{inputtext,textarea,inputnumber,inputgroup,floatlabel}`、`presets/aura/base` 设计令牌。

目标：在 `GuiCore/CustomUI/line_edit/` 下用 PySide6 复刻输入类组件，并新增「输入预览」页面。

> 该页面实际是**整页表单控件总览**（输入框、选择器、开关、数值可视化混排），
> 共 18 个分组、32 个控件实例。本文按依赖关系拆成 4 批实现。

> **实现状态：批次 1–4 全部完成**（整页 21 个分组 / 32+ 实例）。落地文件：
>
> | 文件 | 内容 |
> |------|------|
> | `input_style.py` | 尺寸规格、深浅主题配色、圆角路径、统一字体 |
> | `input_text.py` | `CInputText`（尺寸 / invalid / disabled / 左右图标） |
> | `textarea.py` | `CTextarea`（随内容自动增高） |
> | `input_number.py` | `CInputNumber`（上下步进、范围与小数位） |
> | `input_group.py` | `CInputGroup` + `CInputGroupAddon`（可放图标/文字/复选框） |
> | `float_label.py` | `CFloatLabel`（聚焦/有值时标签上浮） |
> | `choice.py` | `CCheckbox` / `CRadioButton` / `CToggleSwitch` |
> | `toggle_button.py` | `CToggleButton` / `CSelectButton` |
> | `dropdown.py` | `CDropdownField`：下拉字段基类（盒子 + 箭头 + 浮层） |
> | `overlay.py` | `CPopover` / `COptionList` / `CTreeList`（浮层、滚动列表、树列表） |
> | `select.py` | `CSelect` / `CMultiSelect` / `CAutoComplete` / `CTreeSelect` / `CListbox` |
> | `date_picker.py` | `CDatePicker` + `CCalendarPanel` |
> | `slider.py` / `rating.py` / `knob.py` / `color_picker.py` | `CSlider` / `CRating` / `CKnob` / `CColorPicker` |
> | `paint_utils.py` | 勾、叉、箭头、日历、星形等自绘小工具 |
>
> `Apps/input_preview/` —— 输入预览页（21 个分组），与按钮预览并列在左侧菜单；
> `CLineEdit` 保留为 `CInputText` 的兼容壳（沿用 32px 高度）。

---

## 1. 源页面拆解

```vue
<!-- 左栏 -->
<InputText placeholder="Default" />
<InputText placeholder="Disabled" :disabled="true" />
<InputText placeholder="Invalid" invalid />

<IconField><InputIcon class="pi pi-user" /><InputText placeholder="Username" /></IconField>
<IconField iconPosition="left"><InputText placeholder="Search" /><InputIcon class="pi pi-search" /></IconField>

<FloatLabel><InputText id="username" /><label>Username</label></FloatLabel>
<Textarea placeholder="Your Message" :autoResize="true" rows="3" cols="30" />
<AutoComplete dropdown multiple display="chip" placeholder="Search" />
<DatePicker :showIcon="true" :showButtonBar="true" />
<InputNumber showButtons mode="decimal" />

<InputText v-model.number="sliderValue" /><Slider v-model="sliderValue" />
<Rating />  <ColorPicker />  <Knob :step="10" :min="-50" :max="50" />

<!-- 右栏 -->
<RadioButton /> <Checkbox /> <ToggleSwitch />
<Listbox :filter="true" /> <Select placeholder="Select" />
<MultiSelect :filter="true">（自定义 chip 值模板）</MultiSelect>
<TreeSelect placeholder="Select Item" />
<ToggleButton onLabel="Yes" offLabel="No" /> <SelectButton />

<!-- 底部整宽 -->
<InputGroup>  <!-- 4 组 -->
  <InputGroupAddon><i class="pi pi-user" /></InputGroupAddon><InputText placeholder="Username" />
  <InputGroupAddon><i class="pi pi-clock" /></InputGroupAddon>
  <InputGroupAddon><i class="pi pi-star-fill" /></InputGroupAddon>
  <InputNumber placeholder="Price" /><InputGroupAddon>$</InputGroupAddon><InputGroupAddon>.00</InputGroupAddon>
  <Button label="Search" /><InputText placeholder="Keyword" />
  <InputGroupAddon><Checkbox :binary="true" /></InputGroupAddon><InputText placeholder="Confirm" />
</InputGroup>
```

---

## 2. 复刻清单（18 组 / 32 个实例）

| # | 分组 | 数量 | 关键属性 | 批次 |
|---|------|------|----------|------|
| 1 | InputText | 3 | 默认 / `disabled` / `invalid` | **1** |
| 2 | Icons（IconField） | 2 | 图标右（Username）/ 图标左（Search） | **1** |
| 3 | Float Label | 1 | 标签浮动 | **1** |
| 4 | Textarea | 1 | `autoResize`、rows=3 | **1** |
| 5 | InputNumber | 1 | `showButtons`、`mode="decimal"` | **1** |
| 6 | InputGroup | 4 | 图标 addon / 多 addon + 数字 + 货币 / 按钮 + 输入 / 复选框 + 输入 | **1**（复选框版依赖批次 2） |
| 7 | AutoComplete | 1 | `dropdown`、`multiple`、`display="chip"` | 3 |
| 8 | DatePicker | 1 | `showIcon`、`showButtonBar` | 3 |
| 9 | Slider | 2 | 与 InputText 双向联动 | 4 |
| 10 | Rating | 1 | 默认 | 4 |
| 11 | ColorPicker | 1 | 默认 | 4 |
| 12 | Knob | 1 | `step=10`、`min=-50`、`max=50` | 4 |
| 13 | RadioButton | 3 | Chicago / Los Angeles / New York | 2 |
| 14 | Checkbox | 3 | 同上 | 2 |
| 15 | ToggleSwitch | 1 | 默认 | 2 |
| 16 | Listbox | 1 | `filter` | 3 |
| 17 | Select | 1 | `placeholder` | 3 |
| 18 | MultiSelect | 1 | `filter` + 自定义 chip | 3 |
| 19 | TreeSelect | 1 | `placeholder` | 3 |
| 20 | ToggleButton | 1 | `onLabel/offLabel` | 2 |
| 21 | SelectButton | 1 | 3 选项 | 2 |
| | **合计** | **32** | | |

> 表中编号按源码顺序；#7–#21 与 #1–#6 同页，但属于不同控件族，按批次推进。

### 批次划分

| 批次 | 范围 | 状态 |
|------|------|------|
| 1 | 文本输入族：`CInputText`、`CTextarea`、`CInputNumber`、`CInputGroup`（含 addon）、`CFloatLabel` | ✅ 已完成 |
| 2 | 开关/单选族：`CCheckbox`、`CRadioButton`、`CToggleSwitch`、`CToggleButton`、`CSelectButton` | ✅ 已完成 |
| 3 | 选择器族：`CSelect`、`CListbox`、`CMultiSelect`、`CAutoComplete`、`CTreeSelect`、`CDatePicker` | ✅ 已完成 |
| 4 | 数值可视化：`CSlider`、`CRating`、`CKnob`、`CColorPicker` | ✅ 已完成 |

---

## 3. 组件设计（文本输入族）

| 类 | 职责 | 对应实例 |
|----|------|----------|
| `CInputText` | 单行输入：尺寸 / invalid / disabled / 左右图标 | #1、#2 |
| `CTextarea` | 多行输入，支持随内容增高 | #4 |
| `CInputNumber` | 数字输入 + 上下步进按钮 | #5 |
| `CInputGroup` + `CInputGroupAddon` | 横向组合：前缀图标/文字、后缀、按钮、复选框 | #6 |
| `CFloatLabel` | 浮动标签容器（标签随聚焦/有值上浮） | #3 |
| `CLineEdit` | 旧组件，改为 `CInputText` 的兼容壳 | — |

### 3.1 `CInputText` API

```python
CInputText(
    text: str = "",
    placeholder: str = "",
    size: Literal["sm", "md", "lg"] = "md",
    invalid: bool = False,
    icon: str | QIcon | None = None,
    icon_pos: Literal["left", "right"] = "left",
    fluid: bool = True,          # 是否占满父容器宽度
    parent=None,
)
```

- 信号：`textChanged`、`editingFinished`（沿用 `QLineEdit`）；
- 图标用 `QLineEdit.addAction()`，左/右图标的文本内边距自动让位；
- `set_invalid(True)` 走动态属性 `invalid="true"`，由 QSS 属性选择器换边框色。

### 3.2 状态与尺寸

| 状态 | 表现 |
|------|------|
| normal | 深色底 + 中性边框 |
| hover | 边框提亮一级 |
| focus | 边框换成 primary 色（2px 内描边效果） |
| invalid | 边框红 + placeholder 红 |
| disabled | 底色降一级、文字变灰、不可编辑 |

尺寸：`sm` 32px / `md` 40px / `lg` 48px（与 `CButton` 对齐），
字号 14 / 16 / 18，左右内边距 10 / 12 / 14。

### 3.3 `CInputGroup` 组合规则

- `QHBoxLayout(spacing=0)`，相邻元素边框合并；
- 首元素只保留左侧圆角，末元素只保留右侧圆角，中间直角；
- addon 用独立控件绘制（背景比输入框深一级，图标/文字居中，左右内边距 10px）；
- 组内按钮直接复用 `CButton`（同尺寸），输入框用 `CInputText`。

### 3.4 开关 / 选择器 / 数值可视化 API

| 类 | 关键参数 | 信号 |
|----|----------|------|
| `CCheckbox(text, checked)` | 二态复选框 | `toggled(bool)` |
| `CRadioButton(text, checked)` | 同父级自动互斥（Qt autoExclusive） | `toggled(bool)` |
| `CToggleSwitch(text, checked)` | 轨道 40×24，滑块 160ms `OutCubic` 过渡 | `toggled(bool)` |
| `CToggleButton(on_label, off_label, checked)` | 选中实心 / 未选中描边，宽度按较长标签锁定 | `toggled(bool)` |
| `CSelectButton(options, index)` | 分段单选，选中段主色填充 | `selectionChanged(int)` |
| `CSelect(options, value, placeholder, filter)` | 单选下拉，可选过滤器 | `selectionChanged(object)` |
| `CMultiSelect(options, values, filter)` | 多选下拉，芯片展示 + `+N` 溢出 | `selectionChanged(list)` |
| `CAutoComplete(options, values, multiple)` | 可输入 + 下拉建议（Sakai 的 chip 形态） | `selectionChanged(list)` |
| `CTreeSelect(nodes, value)` | 树形下拉（节点 `{"label", "children"}`） | `selectionChanged(str)` |
| `CListbox(options, value, filter, height)` | 内联列表 + 过滤器 | `selectionChanged(object)` |
| `CDatePicker(value, show_button_bar)` | 日历弹层，`yyyy-MM-dd` 显示 | `dateChanged(QDate \| None)` |
| `CSlider(value, minimum, maximum, step)` | 点击跳转 / 拖动 / 滚轮，按 step 量化 | `valueChanged(int)` |
| `CRating(value, maximum)` | 五星，悬停预览 | `valueChanged(int)` |
| `CKnob(value, minimum, maximum, step)` | 270° 圆环，竖向拖动 | `valueChanged(int)` |
| `CColorPicker(color)` | 24 色 Aura 色板弹层 | `colorChanged(str)` |

**浮层约定**：`CPopover` 用 `Qt.Popup`（点外部自动关闭），内部 `COptionList` 支持
滚轮翻页（最多 8 行）与过滤；`CTreeList` 默认全展开，点箭头折叠。弹层与字段的
生命周期由 `CDropdownField` 统一管理（关闭即 `deleteLater`，不会留下悬空引用）。

**绘制约定**：与按钮组件一致——颜色实时读 `input_style.colors()`，
不缓存色值，切换主题后重绘即生效；勾、叉、箭头、日历、星形等用
`paint_utils` 的矢量路径绘制，不依赖位图资源。

---

## 4. 视觉规格（Aura 实测令牌）

| Token | 值 |
|-------|-----|
| padding-x / padding-y | 0.75rem(12px) / 0.5rem(8px) |
| border-radius | 6px |
| 字号 | md 16px、sm 14px、lg 18px |
| 边框宽度 | 1px（focus 时 1px 主色，Aura 用 box-shadow 模拟外扩） |
| transition | 0.2s（当前直接切换，后续可加动画） |

### 颜色（对齐 Aura 语义，取值映射到基座主题）

| Token | 深色主题 | 浅色主题（Aura） |
|-------|----------|------------------|
| background | `custom_dark_one` `#1a1d22` | `#ffffff` |
| disabled background | `custom_dark_two` `#1e2229` | `#e2e8f0` |
| border | `custom_dark_four` `#262b35` | `#cbd5e1` |
| hover border | `custom_bg_two` `#343b48` | `#94a3b8` |
| focus border | `custom_context_color` `#568af2` | `primary` `#10b981`（基座取蓝） |
| invalid border | `#fca5a5` | `#f87171` |
| text | `custom_text_title` `#dce1ec` | `#334155` |
| placeholder | `custom_text_description` `#4f5b6e` | `#64748b` |
| addon background | `custom_dark_three` `#21252d` | `#f8fafc` |

> 输入框没有 severity 维度，只有单一语义色，因此颜色直接用 QSS（`GuiCore/styles.py`）
> 下发，主题切换时由 `CWindow.apply_style()` 重建样式表自动生效；
> 尺寸/字号属于几何量，由组件本地设置。

---

## 5. 目录结构

```
GuiCore/CustomUI/line_edit/
├── __init__.py          # 统一导出 23 个输入组件
├── input_style.py       # 尺寸规格 + 颜色解析 + 圆角路径 + 字体
├── paint_utils.py       # 兼容层（实现已上移到 GuiCore/CustomUI/paint_utils.py）
├── input_text.py        # CInputText
├── textarea.py          # CTextarea
├── input_number.py      # CInputNumber
├── input_group.py       # CInputGroup + CInputGroupAddon
├── float_label.py       # CFloatLabel
├── choice.py            # CCheckbox / CRadioButton / CToggleSwitch
├── toggle_button.py     # CToggleButton / CSelectButton
├── dropdown.py          # CDropdownField（下拉字段基类）
├── overlay.py           # CPopover / COptionList / CTreeList
├── select.py            # CSelect / CMultiSelect / CAutoComplete / CTreeSelect / CListbox
├── date_picker.py       # CDatePicker + CCalendarPanel
├── slider.py            # CSlider
├── rating.py            # CRating
├── knob.py              # CKnob
├── color_picker.py      # CColorPicker
├── line_edit.py         # CLineEdit（兼容壳，继承 CInputText）
└── README.md            # 本文
```

---

## 6. 预览页

`Apps/input_preview`（与 `Apps/button_preview` 并列，左侧菜单各自一项）：

| 卡片 | 内容 |
|------|------|
| 单行输入 | Default / Disabled / Invalid |
| 尺寸 | Small / Default / Large |
| 图标 | 左图标 Username / 右图标 Search |
| 浮动标签 | 空态 / 有值态（标签上浮） |
| 多行输入 | 自动增高，3 行起 |
| 自动补全 | 多选 chip + 下拉建议 |
| 日期选择 | 日历弹层 + Today/Clear |
| 数字输入 | 整数 / 一位小数两种步进 |
| 滑块 | 与左侧输入框双向联动 |
| 评分 | 五星 |
| 颜色选择 | 色块 + 24 色板 |
| 旋钮 | -50 ~ 50，step 10 |
| 单选按钮 | Chicago / Los Angeles / New York |
| 复选框 | 同上 |
| 开关 | Wifi |
| 列表 | 过滤 + 单选 |
| 下拉选择 | 可过滤单选 |
| 多选 | React / Vue chip |
| 树选择 | Documents → Work / Home |
| 切换按钮 | Yes / No |
| 分段单选 | Off / On |
| 输入框组 | 图标 / 金额 / 按钮 / 复选框四种组合 |

共 22 张卡片、覆盖整页 21 个分组（尺寸为基座补充）。

---

## 7. 验收标准

- 各控件在深/浅四套主题下颜色正确、边框与圆角一致；
- 聚焦/悬停/禁用/非法态切换无残影；
- 语言切换页面重建后输入内容不报错、不崩溃；
- 弹层点击外部自动关闭，重复开合不残留控件（`deleteLater` 已覆盖）；
- `tests/test_input_components.py` 共 27 例，覆盖：尺寸、invalid、禁用、图标、
  数字步进、组合圆角、浮动标签，以及复选框/单选互斥/开关进度、切换按钮文案、
  分段单选、下拉选择与关闭、多选芯片、自动补全过滤、树选择、列表过滤、
  日历点选、日期信号、滑块量化与点击定位、评分点选、旋钮步进、颜色校验。
