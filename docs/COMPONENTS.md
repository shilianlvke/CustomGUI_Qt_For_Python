# 组件速查

`customgui.guicore` 共导出 118 个公开名：`custom_ui` 94 个（91 个组件 + `MenuItem` / `Severity` / `Variant`）、
`window` 12 个窗口部件，以及 `Styles`、字体、任务与回调工具。
全部组件由设计令牌驱动，主题切换后重绘即生效。

## 1. 分类总览

| 分类 | 组件 |
| --- | --- |
| 数据 | `CDataTable` `CTableColumn` `CTableModel` `CPaginator` `CDataView` `CPickList` `COrderList` `CTree` `CTreeTable` `CTimeline` |
| 按钮 | `CButton` `CPushButton` `CButtonGroup` `CSplitButton` `CStatusButton` `CMenuButton` `CToggleButton` |
| 输入 | `CInputText` `CLineEdit` `CTextarea` `CInputNumber` `CInputGroup` `CInputGroupAddon` `CFloatLabel` `CSelect` `CComboBox` `CListbox` `CMultiSelect` `CTreeSelect` `CAutoComplete` `CDatePicker` `CCalendarPanel` `CColorPicker` `CSlider` `CKnob` `CRating` `CIconField` `CInputIcon` |
| 选择 | `CCheckbox` `CRadioButton` `CSelectButton` `CToggleSwitch` |
| 菜单 | `CMenu` `MenuItem` `CMenubar` `CTieredMenu` `CMegaMenu` `CPanelMenu` `CContextMenu` `CTabMenu` `CStepper` |
| 展示 | `CCard` `CShowCard` `CPanel` `CBadge` `CChip` `CTag` `CAvatar` `CAvatarGroup` `CPixmap` `CImage` `CCarousel` `CGalleria` `CProgressBar` `CSkeleton` `CDivider` `CHDiv` `CVDiv` `CBreadcrumb` `CSteps` `CPageTransition` |
| 浮层 | `COverlayPanel` `CToolTip` `CDialog` `CConfirmDialog` `CConfirmPopup` |
| 反馈 | `CMessage` `CToast` |
| 文件/图表 | `CFileUpload` `CChart` |
| 布局 | `CFluid` `CTabs` `CAccordion` `CAccordionPanel` `CFieldset` `CFormField` `CFormGrid` `CScrollArea` `CScrollTop` `CSplitter` `CSplitterHandle` `CToolbar` |
| 窗口部件 | `CWindow` `CTitleBar` `CLeftMenu` `CLeftColumn` `CTopColumn` `CBottomColumn` `CGrips` `CCredits` `CAppTopbar` `CAppMenu` `CAppMenuItem` `CAppConfigurator` |

分类只是导航；同名对象都从 `customgui.guicore` 顶层导入。

## 2. 通用约定

- **语义色**：`severity` 接受 `Severity` 枚举或字符串（`primary` / `secondary` / `success` / `info`
  / `warn` / `danger` / `contrast`），并兼容 PrimeVue 的 `error` / `warning` 别名。
- **形态**：`variant` 取 `solid` / `outlined` / `text`；按钮另有 `plain` / `rounded` / `raised`。
- **尺寸**：`size` 取 `sm` / `md` / `lg`，与 `tokens.size.control_height` 对齐。
- **父子关系**：组件不接管父控件生命周期；放进布局后由 Qt 管理，浮层/通知这类顶层部件要传 `parent`。
- **色值不缓存**：自绘组件在 `paintEvent` 里读 `ColorPalette` 或 `get_design_tokens()`，不要在 `__init__` 里存颜色。
- **可调参数**：动画时长、间距、遮罩透明度在 `_resources/customui/settings/window.yaml`
  的 `button` / `page_transition` / `feedback` / `overlay` / `panels` 段（见第 7 节）。

## 3. 常用签名

### 按钮

```python
CButton(text="", icon=None, icon_pos="left", severity="primary", variant="solid",
        plain=False, rounded=False, raised=False, size="md", loading=False,
        fixed_width=None, icon_size=None, focus_ring=True, parent=None)

CButtonGroup(buttons)                 # 同组内边框合并
CSplitButton(text, items=[...])       # items 里 None 表示分隔线
CStatusButton(...)                    # 三态循环（标题栏用）
CMenuButton(...)                      # 带下拉箭头
```

### 输入与选择

```python
CInputText(text="", placeholder="", size="md", invalid=False,
           icon=None, icon_pos="left", fluid=True, corners=None, parent=None)
CTextarea(text="", placeholder="", auto_resize=True, rows=3)
CInputNumber(value=0, minimum=0, maximum=100, step=1, decimals=0)
CSelect(options=(), value=None, placeholder="Select", size="md", filter=False)
CMultiSelect(options=(), values=(), filter=True)
CAutoComplete(options=(), dropdown=False, multiple=False)
CDatePicker(value=None, show_icon=True)
CCheckbox(text="", checked=False)
CToggleSwitch(checked=False)
CSlider(value=0, minimum=0, maximum=100)
CRating(value=0, maximum=5)
```

`CLineEdit` 是 `CInputText` 的兼容壳（固定 32px 高度），新代码用 `CInputText`。

### 数据

```python
CTableColumn(field, header="", width=None, align="left", min_width=90,
             sortable=True, filterable=True, frozen=False,
             formatter=None,                 # (value, record) -> str
             tag=None,                       # (value, record) -> (text, severity)
             expander=False)                 # 可展开详情列

CDataTable(columns=[...], rows=[{...}], page_size=10, paginator=True,
           selection_mode="single", striped=True, gridlines=False,
           frozen_columns=0, group_by=None, empty_text="No records found")

CPaginator(page=0, page_count=1, page_size=10, page_sizes=(5, 10, 20, 50), total=0)
CDataView(rows=[...], item_template=fn, layout="list", columns=2)
CTree(nodes=[...], selection_mode="single")
CTreeTable(columns=[...], rows=[...], checkbox=True, selection_mode="single")
CTimeline(events=[...], align="left", layout="vertical")   # align: left/right/alternate；layout: vertical/horizontal
```

`CTableModel` 负责过滤/排序/分页的数据侧；`CDataTable` 只是视图 + 交互。行数据统一用 `dict`，
列用 `field` 取键。`CDataTable` 的常用方法：`set_rows()` / `set_columns()` / `set_filter()` /
`set_page_size()` / `set_frozen_columns()` / `set_group_by()` / `set_loading()` /
`set_row_detail_provider()` / `selected_records()`。

### 菜单

`CMenu` 是 `QMenu` 子类，菜单项走 Qt 原生 `QAction`，只是外观由基座接管：

```python
menu = CMenu(width=220)
menu.addAction("打开", callback)
action = menu.addAction("删除")
action.setEnabled(False)
menu.addSeparator()
menu.exec(global_pos)             # 或 popup(pos)

# 菜单族共享同一种 items 结构：label / icon / key / items / separator
items = [
    {"label": "文件", "items": [
        {"label": "新建", "icon": "icon_add", "key": "new"},
        {"separator": True},
        {"label": "保存", "icon": "icon_save", "key": "save"},
    ]},
    {"label": "视图", "key": "view"},
]
CMenubar(items)                   # 水平菜单栏
CTieredMenu(items)                # 多级下拉
CMegaMenu(items) / CPanelMenu(items) / CContextMenu(items) / CTabMenu(items)

CStepper(steps=["填写", "确认", "完成"], current=0)
# 另有 add_step(title, content) / set_current(index)
```

### 展示与反馈

```python
CTag(text="运行中", severity="success", rounded=True)
CBadge(text="9", severity="danger", dot=False)
CBadge.attach(target_widget, text="3", severity="danger")
CAvatar(label="张三", shape="circle", size="md")
CProgressBar(value=60, maximum=100, show_value=True)
CSkeleton(width=120, height=16, shape="rect", animation=True)
CDivider(orientation="horizontal", style="solid", text="分组", align="center")

CMessage(text="已保存", title="", severity="success", closable=True,
         show_icon=True, outlined=False, simple=False)
CToast.show_message(parent, "已保存", severity="success", life=3000)
CToast.clear(parent)
```

`CToast` 按窗口分组堆叠，`life=0` 表示不自动消失；同屏上限与停留时长走 `feedback` 设置段。

### 浮层

```python
dlg = CDialog(title="确认", text="内容", width=480,
              accept_text="保存", reject_text="取消", draggable=True)
dlg.add_widget(widget)
ok = dlg.exec_dialog()            # 阻塞，返回是否接受

CConfirmDialog.ask(parent, "删除", "不可撤销", severity="warn")   # -> bool

panel = COverlayPanel(target=button, width=300)
panel.set_content(widget)
panel.toggle()
```

### 布局与表单

```python
CTabs(size="md", tab_position="top", animated=True, closable=False)
tabs.add_tab("基本信息", widget, icon="icon_users")   # -> index

CAccordion(multiple=False)
acc.add_panel("高级", content=widget, expanded=True)   # -> CAccordionPanel

panel = CPanel(title="概览", subtitle="今日", toggleable=True)
panel.content_layout.addWidget(widget)                 # 内容走 content_layout
fields = CFieldset(legend="网络", toggleable=True)
fields.content_layout.addWidget(widget)

CFormGrid(label_position="top", columns=2)
CFormField(label="用户名", field=CInputText(), help_text="登录名", required=True,
           label_position="top")      # top / left / inline / none
grid.add_field("用户名", CInputText(), help_text="登录名", required=True, span=1)

CSplitter(orientation="horizontal")
CToolbar(spacing=8)                   # add_start / add_center / add_end
CScrollArea() / CScrollTop()
```

### 文件与图表

```python
CFileUpload(mode="advanced", accept=[".png", ".pdf"], multiple=True, max_file_size=10 * 1024 * 1024)
CChart(chart_type="line", title="", animation=True, legend=True)
chart.set_data([{"name": "访问量", "values": [3, 5, 8], "labels": ["一", "二", "三"]}])
```

`CChart` 依赖 `PySide6.QtCharts`；缺失时降级为占位提示，不抛异常。
`chart_type` 支持 `line` / `bar` / `pie` / `doughnut` / `polar` / `radar`。

### 壳层

```python
CAppTopbar(title="控制台", logo=icon)      # logo / 菜单开关 / 搜索 / 通知 / 用户菜单
CAppMenu(items=[...])                      # 嵌套侧边菜单
CAppConfigurator(window)                   # 右侧主题配置抽屉
```

壳层组件用于「应用内再套一层后台布局」，与基座主窗口的四向栏目互不替代。

## 4. 窗口部件

| 部件 | 说明 |
| --- | --- |
| `CWindow` | 无边框圆角窗口容器，`set_stylesheet()` 只切换 `frameStyle` 动态属性 |
| `CTitleBar` | 自绘标题栏：logo、标题、菜单按钮、搜索、主题/语言切换、最大化/关闭 |
| `CLeftMenu` | 左侧图标菜单，单选高亮，可折叠（宽度动画） |
| `CLeftColumn` / `CTopColumn` / `CBottomColumn` | 三个方向的栏目抽屉，47px 标题条 + `menus` 堆栈 |
| `CGrips` | 八方向缩放夹点 |
| `CCredits` | 底部版权/版本栏，订阅语言变化 |
| `CAppTopbar` / `CAppMenu` / `CAppMenuItem` / `CAppConfigurator` | 应用壳层 |

右列 `Ui_RightColumn` 由 `customgui.guis` 再导出（实现位于 `guicore.window`）。

## 5. 设计令牌与样式

```python
from customgui.appcore import get_design_tokens, get_theme_manager, ColorPalette
from customgui.guicore import Styles

tokens = get_design_tokens()
tokens.colors.surface_card
tokens.typography.size_text
tokens.spacing.padding_md
tokens.radius.window
tokens.border.width
tokens.size.control_height

Styles()                                  # 生成当前主题的全局 QSS
get_theme_manager().apply("eye")
```

令牌分六组：`colors` / `typography` / `spacing` / `radius` / `border` / `size`。
颜色一律从令牌取，不要在组件里写死十六进制值——四套主题都要能自动适配。

## 6. 预览应用

`apps/` 下的 10 个示例应用就是组件目录的活文档，`customgui install-demo` 后从左侧菜单进入：

| 应用 | 覆盖组件 |
| --- | --- |
| `button_preview` | `CButton` 全形态、按钮组、分体按钮、状态按钮、菜单按钮 |
| `input_preview` | 输入框、文本域、数字、下拉、多选、日期、滑块、评分、开关、输入组 |
| `data_preview` | `CDataView` `CPickList` `COrderList` `CTree` `CTimeline` |
| `table_preview` | `CDataTable` + `CTableColumn` + `CPaginator`（分页、排序、冻结列、分组、行展开） |
| `menu_preview` | 菜单族、`CStepper`、`CTabMenu` |
| `feedback_preview` | `CMessage` `CToast` `CTag` `CBadge` `CChip` `CAvatar` `CSkeleton` `CProgressBar` `CDivider` |
| `overlay_preview` | `CDialog` `CConfirmDialog` `COverlayPanel` + 四向栏目抽屉 |
| `panel_preview` | `CTabs` `CAccordion` `CPanel` `CFieldset` `CToolbar` `CSplitter` `CFormGrid` |
| `media_preview` | `CImage` `CCarousel` `CGalleria` `CPixmap` `CChart` `CFileUpload` |
| `shell_preview` | `CAppTopbar` `CAppMenu` `CAppConfigurator` |

## 7. 设置项速查（`_resources/customui/settings/window.yaml`）

| 段 | 键 | 作用 |
| --- | --- | --- |
| 顶层 | `startup_size` / `minimum_size` | 启动与最小窗口尺寸 |
| 顶层 | `window_border_radius` / `window_margin` / `window_shadow` | 无边框窗口外观 |
| 顶层 | `lef_menu_size` / `left_column_size` / `right_column_size` / `top_column_size` / `bottom_column_size` | 菜单与四向栏目的尺寸区间 |
| 顶层 | `time_animation` | 通用动画时长 |
| `page_transition` | `page_out` / `menu_out` / `menu_in` / `page_in` / `easing` | 栏目切换四段过场 |
| `feedback` | `toast_life` / `toast_max` / `toast_duration` / `toast_margin` / `toast_spacing` / `skeleton_duration` | 通知与骨架屏 |
| `overlay` | `dialog_duration` / `drawer_duration` / `mask_alpha` | 对话框与遮罩（`drawer_duration` 在栏目化后仅兼容保留） |
| `panels` | `tab_duration` / `collapse_duration` / `splitter_handle` / `splitter_grip` | 标签、折叠、分隔条 |
| `button` | `hover_duration` | 按钮悬停过渡 |
| 字体 | `family` / `title_size` / `subtitle_size` / `text_size` | 全局字体与字号 |

主题名与默认语言在 `settings/config.yaml`（`theme_name` / `language` / `logo*`）。
