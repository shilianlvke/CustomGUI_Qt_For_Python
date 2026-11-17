# 自绘弹出菜单（CPopupMenu）

> 位置：`sllkgui.guicore.custom_ui.menu.CPopupMenu`
>
> 一句话：一个不继承 `QMenu` 的弹出菜单——单窗口承载多级面板，全部视觉由
> `QPainter` 绘制，键盘、滚动、贴边翻转与主题配色都在自己手里。

## 1. 为什么不用 `QMenu`

| 限制 | 后果 |
| --- | --- |
| 套用样式表后 Qt 不再绘制子菜单箭头 | 子菜单失去「可点开」的暗示，只能贴图补，且要按主题准备四套 |
| 菜单项只有一种高度、一种字体、一段文本 | 做不了分组标题、右侧元信息、只读状态行（托盘 `status` 槽需要灰显且不可点） |
| 子菜单固定向右展开，贴到屏幕右缘会被整体推回 | 面板压在父菜单上，层级关系被打乱 |
| 多窗口嵌套（父菜单 + 每个子菜单一个 popup） | 「子菜单关了、父菜单还在」的竞态；点外部关闭时行为不确定 |

`CPopupMenu` 用一个 `Qt.Popup` 窗口承载**全部**面板，因此上述问题在架构层面
不存在：hover 链、外部点击、Esc 只有一个事件源。

## 2. 架构

```text
CPopupMenu (Qt.Popup，一个窗口)
├─ 面板 0  根菜单          rect 由锚点 + 屏幕可用区决定
├─ 面板 1  子菜单          rect = 父面板右侧（放不下则左侧），纵向对齐父行
└─ 面板 n  …               每一级都持有 hover / scroll / open_index
```

- 面板矩形按**屏幕坐标**计算，绘制时减去窗口原点；
- 窗口几何 = 所有面板的并集 + `shadow` 留白，因此子菜单展开时窗口整体变大，
  阴影始终包住整组面板；
- `paintEvent` 先画阴影、再逐面板画底与行，行内容用面板圆角路径裁剪。

## 3. 快速开始

```python
from sllkgui.guicore.custom_ui.menu import CPopupMenu, MenuItem, MenuStyle

menu = CPopupMenu([
    MenuItem(label="打开主窗口", key="show"),
    MenuItem(separator=True),
    MenuItem(label="番茄钟", items=[
        MenuItem(label="开始专注", key="start"),
        MenuItem(label="暂停", key="pause", disabled=True),
    ]),
    MenuItem(label="退出", key="quit"),
])
menu.triggered.connect(lambda item: print("clicked", item.key))
menu.popup(QCursor.pos(), above=True, align="right")   # 贴底边向上展开、右对齐
```

## 4. 数据模型：`MenuItem`

菜单族共用同一种结构（与 `CMenu` / `CMenubar` 一致），无需另建模型：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `label` | `str` | 显示文本；超宽自动省略号 |
| `icon` | `str \| QIcon \| None` | 图标名 / 路径 / `QIcon`，按文字色单色渲染 |
| `items` | `list[MenuItem]` | 非空即渲染子菜单箭头 |
| `command` | `Callable[[], None] \| None` | 选中后由组件直接调用 |
| `disabled` | `bool` | 禁用：弱化色、不响应点击、键盘跳过 |
| `separator` | `bool` | 渲染为分隔线 |
| `key` | `str \| None` | 业务标识，随 `triggered` 回传 |
| `checked` | `bool \| None` | `None` 普通项；`True/False` 可勾选项，勾号占图标列 |

## 5. 样式：`MenuStyle`

默认值全部取自主题令牌（`menu_colors()` / `menu_font()`），只覆盖需要改的字段：

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `background` / `border` / `divider` | 主题 | 面板底色、描边、分隔线 |
| `text` / `muted` / `hover` / `accent` | 主题 | 正文、禁用、悬停底色、强调色 |
| `radius` / `row_radius` / `row_inset` | `10 / 6 / 4` | 面板圆角、行圆角、行左右内缩 |
| `row_height` / `separator_height` / `padding` | `34 / 9 / 5` | 密度 |
| `text_padding` / `arrow_space` | `12 / 22` | 文本留白、箭头预留 |
| `icon_size` / `icon_gap` | `16 / 8` | 图标 |
| `min_width` / `max_width` | `180 / 420` | 面板宽度区间 |
| `font_size` / `shadow` | `14 / 14` | 字号与阴影留白 |
| `backdrop_tint` | `0.25` | 模糊底透出比例（0 全按主题底色，1 全透明） |

```python
menu.set_style(MenuStyle(row_height=30, font_size=13, shadow=10))
menu.colors()["background"]      # 查看当前实际生效的配色（主题 + 覆盖）
```

主题切换后无需重建菜单：每次 `paintEvent` 都重新读取令牌。

## 6. 接口

| 方法 | 说明 |
| --- | --- |
| `set_items(items)` | 替换顶层项；菜单打开时会先关闭（几何与 hover 链已失效） |
| `items()` | 取顶层项 |
| `set_style(style)` / `style()` / `colors()` | 样式覆盖与生效配色 |
| `popup(anchor, *, above=True, align="right", gap=6)` | 在全局坐标展开；`anchor` 可传 `QRect`（推荐，托盘图标）或坐标点；`align` 取 `right/left/center`；`gap` 是与锚点的间距 |
| `dismiss()` | 关闭整条链路 |
| `is_open()` | 是否可见 |
| `panel_count()` / `visible_labels()` / `panel_rects()` | 结构诊断（测试与调试） |
| `row_rect(index, depth=0)` | 某一行在屏幕上的矩形（自定义命中 / 自动化测试） |
| `active_label()` / `open_depth()` | 当前高亮项与展开深度 |
| `scroll_offset(depth)` / `content_height(depth)` / `visible_height(depth)` | 滚动状态 |
| `move_active(delta)` | 面板内移动高亮（跳过禁用与分隔线，首尾循环） |
| `set_active_index(index)` | 直接高亮某行（自定义命中） |
| `open_active_submenu()` / `close_submenu()` | 展开 / 收起一级 |
| `activate_active()` | 执行当前高亮项（父项则展开子菜单） |

| 信号 | 触发时机 |
| --- | --- |
| `triggered(MenuItem)` | 选中可执行项；随后自动关闭 |
| `hovered(MenuItem)` | 高亮项变化（鼠标或键盘），用于联动态提示 |
| `aboutToShow()` | `popup()` 布局完成后、显示前 |
| `aboutToHide()` | 完全关闭后（含点外部、Esc、失活） |
| `closed()` | 同上，语义化别名 |

## 7. 交互

| 输入 | 行为 |
| --- | --- |
| 悬停行 | 高亮；若该行有子菜单，150ms 后自动展开 |
| 悬停已展开的父行 | **保持子菜单打开**（从箭头移向子菜单的必经路径） |
| 悬停另一个父行 | 收起已展开的下一级，再按该行决定是否展开 |
| 点击父行 | 立即展开（不等延迟） |
| 点击普通行 | 发 `triggered` → 关闭；可勾选项先翻转并发 `toggled` |
| 滚轮 | 在指针所在面板滚动，一次 3 行；滚动时收起该面板子菜单 |
| `↑` `↓` | 当前面板内移动，跳过禁用与分隔线，首尾循环 |
| `→` | 展开子菜单并把高亮移到子菜单第一项 |
| `←` | 收起一级，高亮回到父行 |
| `Enter` / `Space` | 执行；父项则展开；可勾选项先翻转再执行 |
| `Home` / `End` | 跳到首 / 尾可选项，并滚入可视区 |
| `Esc` | 有子菜单先收一级，否则整体关闭 |
| `Tab` | 直接关闭 |

关闭条件：点击菜单外部（`Qt.Popup` 语义）、窗口失活（Alt+Tab / 切应用）、
执行完动作、`dismiss()`、`Esc` 到根级。

### 7.1 勾选态

```python
MenuItem(label="开机自启", key="autostart", checked=True)    # 已选中
MenuItem(label="声音提示", key="sound", checked=False)        # 未选中
MenuItem(label="普通项", key="plain")                         # checked=None
```

- 勾号画在**图标列**内（10px、1.6px 圆头描边、强调色），与原生菜单一致；
- 可勾选项不再绘制自己的 `icon`：一列只放一个视觉元素，避免「图标 + 勾」挤在一起；
- 点击或 `Enter`/`Space` 翻转 `item.checked`，先发 `toggled(item, checked)`
  再发 `triggered`，随后关闭菜单（与原生行为一致）；
- 禁用项（`disabled=True`）不可翻转，勾号用弱化色；
- `checked` 是**值对象上的状态**：菜单不保存副本，宿主每次 `set_items` 重建时
  需把最新状态写回（托盘是每次打开前重新编译菜单项，天然满足）。

### 7.2 图标列对齐

- 面板内只要有**一条**带 `icon` 或可勾选的行，整列留出
  `icon_size + icon_gap`（默认 24px），所有文案从同一起点开始；
- 没有图标也没有勾选项的面板不留空列，避免窄菜单出现莫名缩进；
- 图标与勾号都按 16px 列宽**水平居中、垂直居中**，不随文字长度抖动；
- 列宽按面板独立计算（与原生菜单一致），子菜单不会继承父面板的列宽。

### 7.3 亚克力质感

```text
popup()
  ├─ 判定：底色 alpha < 250（glass_surface 决定，支持亚克力且开启质感才成立）
  ├─ 截屏 screen.grabWindow(0) → 缩到 1/16 → 放大到 1/4（低成本高斯近似）
  └─ 绘制：按屏幕坐标把模糊图贴进面板圆角路径，再叠 75% 主题底色
```

- 模糊图**整屏只截一次**，子菜单展开导致窗口变大/左移时按屏幕坐标重新裁切，
  不会把菜单自己拍进去；
- `backdrop_tint` 控制透出比例，默认 0.25（底色 alpha 约 0.75），下限 90
  保证亮色桌面下文字仍可读；
- 阴影只画在面板**之外**（用面板圆角路径从窗口区域里减掉），否则半透明面板
  会把阴影透上来发灰；
- 关闭时释放模糊图；`uses_backdrop() == False`（不透明底色）时**完全不截屏**，
  零额外开销；
- 只覆盖锚点所在屏：菜单跨屏时另一侧只有底色，不会串用别屏的模糊。

## 8. 边界处理

| 场景 | 处理 |
| --- | --- |
| 锚点贴近屏幕右边 | 根面板右对齐到锚点（`QRect` 时即图标右缘），越界时夹紧；子菜单放右侧会越界时自动**向左翻转** |
| 锚点在任务栏里（托盘图标） | 以图标外接矩形为锚点、向上留 6px 间距；底边夹到可用区底部，不压住任务栏 |
| 两侧都放不下（超宽面板） | 压回屏内，允许与父面板重叠，至少保证可见 |
| 内容高于屏幕 | 面板高度夹紧到可用区，启用滚动 + 上下箭头提示；键盘移动会把目标行滚入视野 |
| 子菜单纵向越界 | 面板顶部夹紧到可用区内，仍与父行保持同侧 |
| 多显示器 | 以锚点所在屏的 `availableGeometry()` 为边界 |
| 面板贴边 | 面板本体距可用区至少 4px；阴影允许出屏，由系统裁掉 |
| 空菜单 | 只渲染面板与内边距，不产生空行 |
| 打开时条目变化 | `set_items` 先关闭再替换，避免点到「刚消失的位置」 |

## 9. 替换现有 `QMenu` 的要点

| `QMenu` 用法 | `CPopupMenu` 写法 |
| --- | --- |
| `menu.addAction(text)` | `MenuItem(label=text)` 放进列表 |
| `action.setEnabled(False)` | `MenuItem(disabled=True)` |
| `menu.addSeparator()` | `MenuItem(separator=True)` |
| `menu.addMenu(title)` | `MenuItem(label=title, items=[...])` |
| `action.triggered.connect(cb)` | 统一接 `menu.triggered`，按 `item.key` 分发（或写 `item.command`） |
| `menu.exec(pos)` | `menu.popup(pos, above=..., align=...)` |
| `menu.popup(pos)` | 同上；无需再算翻转，组件自己处理 |
| `menu.aboutToShow` | `aboutToShow` 信号（在 `popup()` 内发出） |
| `menu.clear()` | `menu.set_items([...])` |
| `QSystemTrayIcon.setContextMenu(menu)` | **不要设置**：改用 `activated(Context)` 里调 `show_menu()` |

迁移时注意：

1. **不要保留 `QAction` 引用**：条目是值对象，重建列表即可，状态（禁用）写在
   `MenuItem` 上；
2. **在 `popup()` 之前重建条目**：菜单每次打开前刷新数据，避免菜单里的项与
   真实状态不一致；
3. **弹层不再有原生无障碍树**：`QMenu` 会被读屏器识别为菜单，自绘控件需要
   通过 `setAccessibleName`（已设「菜单」）与后续 `QAccessibleInterface` 补齐；
4. **勾选态用 `MenuItem.checked`**：`QAction.setCheckable(True)` 对应
   `checked=False`，`setChecked()` 对应改 `item.checked` 后 `update()`；
5. **不要用 `palette()` 这个名字**暴露配色：会覆盖 `QWidget.palette()`，
   组件用的是 `colors()`。

## 10. 参考实现

托盘菜单是第一个落地场景：

```python
# sllkgui/gallery/tray.py
def show_menu(self, anchor=None):
    menu = self._ensure_menu()          # CPopupMenu(self.menu_items())
    self._rebuild_menu()
    menu.popup(anchor or QCursor.pos(), above=True, align="right")
```

`TrayPlan`（槽 → 插件块 → 兜底桶）编译成 `MenuItem` 树的逻辑在
`TrayService.menu_items()`，与渲染完全解耦，方便测试与将来做「托盘管理器」。

## 11. 已知限制

| 项 | 说明 |
| --- | --- |
| 无障碍 | 只设置了 `accessibleName`，没有完整的 `QAccessible` 角色与子节点 |
| 跨屏模糊 | 只截锚点所在屏；菜单跨显示器时另一侧仅显示底色 |
| 亚克力来源 | 截屏 + 缩放模糊，不调用系统 DWM，透明区域不会穿透点击 |
| 输入法 | 菜单不接收文本输入，中文输入法弹窗不受影响 |
