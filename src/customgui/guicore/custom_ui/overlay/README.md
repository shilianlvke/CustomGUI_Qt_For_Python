# 浮层组件复刻（P1）

复刻对象：Sakai 的 **Overlay** 页（<https://sakai.primevue.org/uikit/overlay>），
样式依据 `@primeuix/themes` 的 Aura `dialog` / `confirmdialog` / `overlaypanel` 预设。

目标：给业务页面补齐“弹出层”能力——对话框、确认框、跟随锚点的浮层，
统一遮罩、动画、关闭方式与层级管理。

## 1. 落地内容

| 文件 | 组件 | 能力 |
|------|------|------|
| `overlay/base.py` | `_OverlayBase` | 全窗口遮罩、卡片定位、淡入淡出、ESC / 点遮罩关闭、`exec_dialog()` |
| `overlay/card.py` | `COverlayCard` | 浮层卡片：圆角、描边、主题底色 |
| `overlay/dialog.py` | `CDialog` | 标题 + 正文 + 底部按钮；可拖动；sm/md/lg/xl 或自定义宽度 |
| `overlay/confirm.py` | `CConfirmDialog` | 语义图标 + 确认文案 + 接受/拒绝，`ask()` 阻塞式助手 |
| `overlay/panel.py` | `COverlayPanel` | 跟随目标控件的浮层，点击外部自动关闭 |

共用件：`GuiCore/CustomUI/close_button.py` 的 `CCloseButton`（消息、通知、浮层统一使用）。

> `GuiCore.CDialog` 已指向新的浮层版对话框；旧的窗口式实现仍保留在
> `GuiCore.AppDefineUI.CDialog`，需要旧外观的代码可显式引用。

> **抽屉去哪了**：四向抽屉不再由浮层实现，而是主窗口四周的「栏目」组件——
> 左列 `CLeftColumn`、右列 `Ui_RightColumn`（基座既有），顶列 `CTopColumn` 与
> 底列 `CBottomColumn`（与左列同构，见 `guicore/window/top_column/`、
> `guicore/window/bottom_column/`）。开合动画与按钮路由见
> `guis/windows/main_window/functions.py` 的 `toggle_*_column`。

## 2. 关键 API

```python
CDialog(title="", text="", width=480, accept_text="", reject_text="",
        closable=True, dismissable_mask=True, draggable=True, parent=None)
#   content_layout / add_widget(widget) / add_footer_button(...)
#   open_dialog() / accept() / reject() / exec_dialog() -> bool
#   信号：opened / closed / accepted / rejected

CConfirmDialog(title="Confirm", message="", severity="warn",
               accept_text="Yes", reject_text="No", parent=None)
CConfirmDialog.ask(parent, title, message, severity) -> bool   # 阻塞式

COverlayPanel(target, width=300)
#   set_content(widget) / open_panel() / close_panel() / toggle() / is_open()
#   信号：toggled(bool)
```

- 点击卡片外区域或按 ESC 关闭（可关）；
- 底部按钮默认「拒绝（outlined）+ 接受（primary）」，也可用 `add_footer_button` 追加；
- 需要一次性使用时设置 `dialog.setAttribute(Qt.WA_DeleteOnClose, True)`，关闭后自动销毁；
- `exec_dialog()` 内部用 `QEventLoop` 等待 `accepted / rejected / closed`，不依赖 `QDialog.exec()`。

## 3. 交互与视觉

- 遮罩透明度、动画时长来自 `window.yaml` 的 `overlay` 段（`drawer_duration` 自抽屉
  改为栏目实现后不再被浮层读取，仅为兼容保留）；
- 卡片底色取设计令牌的 `surface_app`（深色主题与旧的 `custom_bg_one` 等价，
  浅色主题不再是纯白，跟 `eye`/`bright` 的板面同色）；描边取 `display.palette.tokens()`；
- 标题栏可拖动（限制在遮罩范围内），拖动时不会移出窗口；
- 对话框圆角 10px；正文包在透明滚动区里：不超高时按内容高度自适应，超高时封顶内滚；
- 浮层是独立顶层窗口，主窗口最大化/还原/拖边框后会跟着重贴边（父窗口 `Resize`/`Move`
  事件延到下一轮事件循环再算，避免读到布局前的旧锚点尺寸）；
- 遮罩绘制前会先把脏区清成透明：透明窗口不做背景擦除，局部重绘会把遮罩再叠一层，
  卡片边缘会出现一串越来越密的竖线（最大化时最明显）。

## 4. 四向抽屉（栏目）

| 方向 | 组件 | 停靠位置 | 开合 |
|------|------|----------|------|
| 左 | `CLeftColumn`（`window/left_column/`） | `window.layout`，菜单栏右侧 | `toggle_left_column` 动画 `minimumWidth` |
| 右 | `Ui_RightColumn`（`window/right_column/`） | 内容区右缘 | `toggle_right_column` 动画 `minimumWidth` |
| 上 | `CTopColumn`（`window/top_column/`） | 标题栏下方、内容区上方 | `toggle_top_column` 动画 `minimumHeight` |
| 下 | `CBottomColumn`（`window/bottom_column/`） | 内容区下方、版权栏上方 | `toggle_bottom_column` 动画 `minimumHeight` |

- 顶/底列与左列同构：47px 标题条 + 圆角标题胶囊（`#CTopColumnTitle_Frame` 等）+
  30×30 图标位 + 30×30 关闭按钮（对象名 `btn_close_top_column` / `btn_close_bottom_column`），
  关闭信号沿 `clicked/released` 汇入主窗口按钮总线，由 `ColumnController` 统一切换；
- 内容区是 uic 生成的 `Ui_TopColumn` / `Ui_BottomColumn`（`menus` 堆栈 + 透明滚动区），
  `set_top_column_menu(menu, title, icon_path)` / `set_bottom_column_menu(...)` 与
  `set_left_column_menu` 用法一致；
- 尺寸区间在 `window.yaml` 的 `top_column_size` / `bottom_column_size`
  （默认 0~240，与左/右列一致）；同侧互斥由动画组保证（开一关一）。

## 5. 可调参数（`customgui/resource/customui/settings/window.yaml`）

```yaml
overlay:
  dialog_duration: 160   # 对话框淡入淡出
  drawer_duration: 200   # 抽屉滑入滑出（栏目化后不再读取，保留兼容）
  mask_alpha: 120        # 遮罩压暗程度（0-255）
```

对应 `AppCore/SYS/config/schema.py` 的 `OverlaySettings`。

## 6. 预览页

`Apps/overlay_preview`（左侧菜单「浮层预览」）共 4 张卡片：

| 卡片 | 内容 |
|------|------|
| 对话框 | 基础（可拖动/可关闭）/ 无标题 / 大尺寸 640 |
| 抽屉 | 左（软件信息）、右（通知）、上（筛选）、下（详情）四个方向的开合按钮 |
| 确认框 | info / success / warn / error 四种语义 |
| 浮层面板 | 点击按钮展开账户浮层，点外部关闭 |

确认/保存后会弹出 `CToast` 反馈，顺带演示 P0 与 P1 的联动。

## 7. 验收

- `tests/test_overlay_components.py`：对话框居中/接受/ESC/无标题、确认框信号、浮层跟随锚点与开合；
- `tests/test_window_columns.py`：顶/底列与左列同构（对象名、47px 标题条、menus 堆栈）、
  开合动画（高度主轴、开一关一）、左列宽度动画回归、关闭按钮路由与 ACTION_MAP；
- 深/浅主题分别核对对话框、确认框、浮层面板与四向抽屉；
- `ruff check` / `ruff format --check` 通过，全量测试保持绿色。
