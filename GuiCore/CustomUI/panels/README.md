# 面板与布局组件（复刻 Sakai / PrimeVue Panels + FormLayout）

> 对应 Sakai 的两个页面：
>
> - `https://sakai.primevue.org/uikit/panels`（源码 `src/views/uikit/PanelsDoc.vue`）
> - `https://sakai.primevue.org/uikit/formlayout`（源码 `src/views/uikit/FormLayout.vue`）
>
> 本文是这一批的统计、设计定稿与实施记录。

---

## 1. 统计

### 1.1 Panels 页：7 个分组

| 分组 | 实例 | 组成 |
|---|---|---|
| Toolbar | 1 | 左（3 个图标按钮）/ 中（搜索框）/ 右（SplitButton） |
| Accordion | 1 组 3 面板 | 单开模式，默认展开第 1 个 |
| Tabs | 1 组 3 标签 | 标签栏 + 内容区 |
| Panel | 1 | 可折叠，header + 正文 |
| Fieldset | 1 | 可折叠，legend + 正文 |
| Card | 1 | 标题行 + 右上角菜单按钮 + 正文 |
| Divider | 2 | 垂直 / 水平（`CDivider` 已有，本轮复用） |
| Splitter | 1 组 3 面板 | 水平 + 嵌套垂直，按比例 30/70、15/50 |

### 1.2 FormLayout 页：6 个分组、15 个字段

| 分组 | 字段 | 布局特征 |
|---|---|---|
| Vertical | Name / Email / Age | 单列，标签在控件上方 |
| Vertical Grid | Name / Email | 两列并排，标签在控件上方 |
| Horizontal | Name / Email | 标签左、控件右（标签约占 1/6 宽） |
| Inline | Firstname / Lastname / Submit | 标签隐藏，控件同行排列 |
| Help Text | Username | 控件下方一行帮助文本 |
| Advanced | Firstname / Lastname / Address / State / Zip | 混合：两列 + 整行 Textarea + 两列 |

归并后只需：**一个栅格容器 `CFormGrid` + 一个字段容器 `CFormField`**，
用 `label_position`（top / left / inline / none）与 `columns`、`span` 覆盖全部 6 组。

---

## 2. 组件清单

目录：`GuiCore/CustomUI/panels/`

| 类 | 说明 | 覆盖分组 |
|---|---|---|
| `CTabs` | 标签页容器：自绘标签栏、滑动指示条、可关闭、图标、禁用、top/bottom | Tabs |
| `CAccordion` + `CAccordionPanel` | 手风琴：单开/多开、高度动画、chevron 旋转 | Accordion |
| `CPanel` | 可折叠面板：标题 + 副标题 + 右侧扩展位 + 底部栏 | Panel |
| `CFieldset` | 图例分组框：legend 嵌在边框上，可折叠 | Fieldset |
| `CToolbar` | 三段式工具栏：start / center / end | Toolbar |
| `CSplitter` | 可拖拽分割：水平/垂直/嵌套、最小尺寸、抓手绘制 | Splitter |
| `CFormGrid` + `CFormField` | 表单栅格：标签位置、多列、跨列、必填星号、帮助文本 | FormLayout 全部 |
| `CBreadcrumb` | 面包屑（补充件，页面头部常用） | — |
| `CSteps` | 步骤条（补充件，向导/流程页常用） | — |

`CCard` 本轮扩展：支持 `title` / `subtitle` / `header_widgets` / `footer`，
用于 Panels 页的「Card + 右上角菜单」形态；不传这些参数时行为与原来完全一致。

---

## 3. API 设计

### 3.1 CTabs

```python
tabs = CTabs(size="md", tab_position="top", animated=True)
index = tabs.add_tab("Header I", content_widget, icon="icon_users", closable=False)
tabs.insert_tab(index, "Header II", widget)
tabs.remove_tab(index)
tabs.set_current_index(index, animate=True)
tabs.current_index(); tabs.current_widget(); tabs.count()
tabs.set_tab_text(index, text); tabs.set_tab_enabled(index, False)
tabs.set_tab_visible(index, False)
# 信号
tabs.currentChanged(int)      # 当前页变化
tabs.tabCloseRequested(int)   # 点了标签上的 ×（默认不自动删除，交给调用方）
tabs.tabBarClicked(int)       # 点击任意标签（含已选中项）
```

- 标签栏自绘：`sm/md/lg` 三档高度（34 / 40 / 46），激活项文字用主色 + 2px 指示条；
- 指示条用 `QVariantAnimation` 在旧位置与新位置之间滑动（时长 `panels.tab_duration`）；
- 标签总宽超出时按最小宽度压缩并 `elidedText` 省略，不出现横向滚动条；
- 键盘：`←/→/Home/End` 切换，`Enter/Space` 激活；
- 内容区用 `QStackedWidget`，切换不做淡入（避免与页面级转场叠加）。

### 3.2 CAccordion

```python
acc = CAccordion(multiple=False, animated=True)
panel = acc.add_panel("Header I", content_widget, icon=None)
panel.content_layout.addWidget(...)      # 不传 content 时直接用这个布局
panel.set_expanded(True); panel.is_expanded(); panel.toggle()
acc.set_active(index); acc.active_index(); acc.panel(i); acc.count()
# 信号
acc.panelToggled(int, bool)
panel.expandedChanged(bool)
```

- 单开模式下展开新面板会收起其它面板；
- 内容高度用 `maximumHeight` 动画（`panels.collapse_duration`，`OutCubic`）；
- chevron 用矢量绘制并按展开进度旋转 90°。

### 3.3 CPanel

```python
panel = CPanel("Header", subtitle="", toggleable=True, collapsed=False)
panel.content_layout.addWidget(...)
panel.add_header_widget(CButton(icon="icon_plus"))
panel.set_footer(widget)                 # 底部栏（带顶部分隔线）
panel.set_expanded(True); panel.is_expanded(); panel.toggle()
```

### 3.4 CFieldset

```python
fs = CFieldset("Legend", toggleable=True, collapsed=False)
fs.content_layout.addWidget(...)
fs.set_legend("Legend"); fs.set_expanded(True)
```

### 3.5 CToolbar

```python
bar = CToolbar()
bar.add_start(CButton(icon="icon_plus"))
bar.add_center(search_input)
bar.add_end(split_button)
bar.start_layout / bar.center_layout / bar.end_layout   # 也可直接塞布局
```

### 3.6 CSplitter

```python
split = CSplitter("horizontal", handle_width=8)
split.add_panel(left_widget, size=30, min_size=12)
split.add_panel(right_widget, size=70)
split.set_sizes([30, 70]); split.sizes()
```

- 基于 `QSplitter`，拖拽/最小尺寸/嵌套由 Qt 负责；
- 抓手为自绘：默认一条 1px 分隔线 + 居中短握把，hover/拖动时主色高亮；
- `setChildrenCollapsible(False)`，避免误拖成 0 宽。

### 3.7 CFormGrid / CFormField

```python
form = CFormGrid(label_position="top", columns=2, label_width=96, spacing=12)
form.add_field("Name", CInputText(), required=True)
form.add_field("Email", CInputText(), help_text="用于找回密码")
form.add_row([("Firstname", CInputText()), ("Lastname", CInputText())])
form.add_widget(CTextarea(rows=4), span=2)     # 整行控件
```

- `label_position`：`top`（垂直）/ `left`（水平）/ `inline`（标签自然宽度，同行）/ `none`（隐藏标签）；
- `required=True` 在标签后画红色 `*`；
- `help_text` 用 `text_size` 字号、次要色显示在控件下方；
- `columns` 控制一行最多几个字段，`span` 跨列。

### 3.8 CBreadcrumb / CSteps

```python
crumb = CBreadcrumb(["Home", "Components", "Panels"])
crumb.add_item("Detail", icon="icon_file", command=fn)
crumb.itemClicked.connect(fn)

steps = CSteps(["Account", "Personal", "Payment", "Confirm"], active=1)
steps.set_active(2); steps.stepClicked.connect(fn)
```

---

## 4. 视觉规格（对齐 Aura 比例）

| 项 | 取值 |
|---|---|
| 面板圆角 | 8px（`CPanel` / `CFieldset` / `CToolbar`），`CTabs` 容器 8px |
| 面板描边 | 1px，`tokens()["border"]` |
| 面板底色 | 深色 `custom_bg_one`，浅色 `#ffffff` |
| Panel header | 高 46，左右 16，标题 15px DemiBold，底部分隔线 |
| Panel 内容 | 左右 16、上下 14，spacing 10 |
| Accordion header | 高 44，左右 16，hover 底色为 `surface` 的 6% 叠加 |
| Tabs 标签 | 水平内边距 14，图标 16 + 间距 8，关闭按钮 16 |
| Tabs 指示条 | 2px，主色，位于标签底部（`tab_position="bottom"` 时在顶部） |
| Fieldset | legend 左右各留 6px 空隙，legend 字号 13 DemiBold |
| Toolbar | 内边距 10 × 14，三段间距 8 |
| Splitter 抓手 | 宽 8，握把长 28、宽 2，圆角 1 |
| Form 标签 | `text_size`（12）→ 实际用 13px，左对齐；水平模式固定 `label_width` |
| 必填星号 | `custom_red`，与标签间距 2px |
| 帮助文本 | 12px，`muted` |

所有颜色**实时读取** `tokens()` / `ColorPalette`，不缓存色值，切换主题后重绘即生效。

---

## 5. 配置项（`customgui/resource/customui/settings/window.yaml`）

```yaml
# PANELS 面板/标签/折叠（毫秒 / 像素）
panels:
  tab_duration: 180        # 标签指示条滑动
  collapse_duration: 180   # 手风琴/面板展开收起
  splitter_handle: 8       # 分割条宽度
  splitter_grip: 28        # 分割条握把长度
```

对应 `AppCore/SYS/config/schema.py` 的 `PanelSettings`，全部带默认值，旧配置缺省也能跑。

---

## 6. 预览页

新增 `Apps/panel_preview`（左侧菜单「面板预览」），每组一张 `CCard`：

| 卡片 | 内容 |
|---|---|
| Toolbar | 左 3 图标按钮 + 中搜索框 + 右保存按钮 |
| Tabs | 基础 4 标签（含禁用项）+ 可关闭 2 标签 + bottom 位置 |
| Accordion | 单开（3 面板带图标）+ 多开（2 面板默认全展开） |
| Panel | 带副标题面板 + 默认收起的可折叠面板 |
| Fieldset | 基础 + 默认收起的可切换 |
| Splitter | 垂直分割器（上/下各 50%） |
| Form Layout | 两列 Firstname/Lastname（必填星号）+ 整行 Bio（帮助文本） |
| Navigation | Breadcrumb（3 级）+ Steps（4 步，激活第 2 步） |

---

## 7. 本轮一并处理的技术债

| 项 | 方案 |
|---|---|
| 按钮 hover/pressed 颜色直切 | 用 `QVariantAnimation` 在两种状态色之间插值，时长 `button.hover_duration`（Aura 0.2s） |
| 高 DPI 图标糊 | 图标栅格化按 `devicePixelRatioF()` 生成并 `setDevicePixelRatio`，缓存键带 dpr |
| 对话框内容超高被截断 | 正文放进透明 `QScrollArea`，卡片高度按内容自适应并封顶，超出时内滚 |
| 抽屉无法调宽 | 内侧边缘加 6px 拖拽条，拖动实时改宽度并重排（240 ~ 父宽-80） |

---

## 8. 实施顺序

1. `panels/style.py` + 配置项；
2. `CTabs` → `CAccordion` → `CPanel` → `CFieldset` → `CToolbar` → `CSplitter`；
3. `CFormGrid` / `CFormField`；
4. `CBreadcrumb` / `CSteps`；
5. `Apps/panel_preview`；
6. 技术债四项；
7. 测试、文档、提交。

## 9. 验收标准

- 深/浅主题下：面板底色、描边、hover、激活指示条颜色正确，无深色残留；
- Tabs 切换时指示条平滑滑动，标签过多时省略而不溢出；
- Accordion 单开/多开正确，快速连点不残留半开高度；
- Splitter 拖动时两侧面板按最小尺寸受限，嵌套分割正常；
- Form 六种布局与 Sakai 截图结构一致，必填星号与帮助文本位置正确；
- 语言切换重建页面后组件全部正常（中英文标签）；
- 新增 `tests/test_panel_components.py`，覆盖上述交互；
- `ruff check` / `ruff format --check` / 全量 pytest 通过。
