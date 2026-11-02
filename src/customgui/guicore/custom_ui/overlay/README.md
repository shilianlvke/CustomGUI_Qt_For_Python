# 浮层组件复刻（P1）

复刻对象：Sakai 的 **Overlay** 页（<https://sakai.primevue.org/uikit/overlay>），
样式依据 `@primeuix/themes` 的 Aura `dialog` / `drawer` / `confirmdialog` / `overlaypanel` 预设。

目标：给业务页面补齐“弹出层”能力——对话框、侧边抽屉、确认框、跟随锚点的浮层，
统一遮罩、动画、关闭方式与层级管理。

## 1. 落地内容

| 文件 | 组件 | 能力 |
|------|------|------|
| `overlay/base.py` | `_OverlayBase` | 全窗口遮罩、卡片定位、淡入淡出、ESC / 点遮罩关闭、`exec_dialog()` |
| `overlay/card.py` | `COverlayCard` | 浮层卡片：圆角、描边、主题底色 |
| `overlay/dialog.py` | `CDialog` | 标题 + 正文 + 底部按钮；可拖动；sm/md/lg/xl 或自定义宽度 |
| `overlay/drawer.py` | `CDrawer` | 左/右/上/下四向滑入；停靠在内容区四边，头部与「软件信息」左抽屉同构 |
| `overlay/confirm.py` | `CConfirmDialog` | 语义图标 + 确认文案 + 接受/拒绝，`ask()` 阻塞式助手 |
| `overlay/panel.py` | `COverlayPanel` | 跟随目标控件的浮层，点击外部自动关闭 |

共用件：`GuiCore/CustomUI/close_button.py` 的 `CCloseButton`（消息、通知、浮层统一使用）。

> `GuiCore.CDialog` 已指向新的浮层版对话框；旧的窗口式实现仍保留在
> `GuiCore.AppDefineUI.CDialog`，需要旧外观的代码可显式引用。

## 2. 关键 API

```python
CDialog(title="", text="", width=480, accept_text="", reject_text="",
        closable=True, dismissable_mask=True, draggable=True, parent=None)
#   content_layout / add_widget(widget) / add_footer_button(...)
#   open_dialog() / accept() / reject() / exec_dialog() -> bool
#   信号：opened / closed / accepted / rejected

CDrawer(title="", position="right", size=320, closable=True, dismissable_mask=True,
        parent=None, *, anchor=None, icon="icon_setting", resizable=True, modal=False)
#   位置支持 left / right / top / bottom，滑入方向由位置决定；
#   anchor 为停靠范围，默认取主窗口 ui.content_area_frame（内容区）；
#   add_widget(w) 追加内容（自动排在末尾弹性空间之前），content_layout 也可直接用；
#   header / title_label / content_layout / bounds() / set_title() / set_icon()

CConfirmDialog(title="Confirm", message="", severity="warn",
               accept_text="Yes", reject_text="No", parent=None)
CConfirmDialog.ask(parent, title, message, severity) -> bool   # 阻塞式

COverlayPanel(target, width=300)
#   set_content(widget) / open_panel() / close_panel() / toggle() / is_open()
#   信号：toggled(bool)
```

- 对话框铺满父窗口；抽屉的遮罩只铺满**内容区**，左侧菜单、标题栏、版权栏不受影响；
- 点击卡片外区域或按 ESC 关闭（可关）；抽屉默认非模态，打开时仍可操作标题栏与菜单；
- 底部按钮默认「拒绝（outlined）+ 接受（primary）」，也可用 `add_footer_button` 追加；
- 需要一次性使用时设置 `dialog.setAttribute(Qt.WA_DeleteOnClose, True)`，关闭后自动销毁；
- `exec_dialog()` 内部用 `QEventLoop` 等待 `accepted / rejected / closed`，不依赖 `QDialog.exec()`。

## 3. 交互与视觉

- 遮罩透明度、动画时长来自 `window.yaml` 的 `overlay` 段；
- 对话框淡入淡出（`dialog_duration`），抽屉滑入滑出（`drawer_duration`）；
- 卡片底色取设计令牌的 `surface_app`（深色主题与旧的 `custom_bg_one` 等价，
  浅色主题不再是纯白，跟 `eye`/`bright` 的板面同色）；描边取 `display.palette.tokens()`；
- 标题栏可拖动（限制在遮罩范围内），拖动时不会移出窗口；
- 抽屉贴边无圆角，对话框圆角 10px；抽屉的阴影按滑入方向落在朝向内容的一侧；
- 对话框正文包在透明滚动区里：不超高时按内容高度自适应，超高时封顶内滚（滚轮可滚），
  正文不再被截断；抽屉正文同样在滚动区里，内容贴顶排列；
- 抽屉头部与 `CLeftColumn`（「软件信息」左抽屉）同构：47px 标题条 + 圆角胶囊
  （`#CLeftColumnTitle_Frame`）+ 30×30 图标位 + 30×30 关闭按钮，直接复用同一批
  样式表对象名，主题切换自动跟随；
- 抽屉可拉伸：朝向内容的内侧有 6px 拖拽热区（left/right 拖宽、top/bottom 拖高），
  悬停显示主色细线，拖动实时重排，尺寸限制在 200 ~ 内容区主轴-80。
- 浮层是独立顶层窗口，主窗口最大化/还原/拖边框后会跟着重贴边（父窗口 `Resize`/`Move`
  事件延到下一轮事件循环再算，避免读到布局前的旧锚点尺寸）；
- 遮罩绘制前会先把脏区清成透明：透明窗口不做背景擦除，局部重绘会把遮罩再叠一层，
  卡片边缘会出现一串越来越密的竖线（滑入、最大化时最明显）。

## 4. 可调参数（`customgui/resource/customui/settings/window.yaml`）

```yaml
overlay:
  dialog_duration: 160   # 对话框淡入淡出
  drawer_duration: 200   # 抽屉滑入滑出
  mask_alpha: 120        # 遮罩压暗程度（0-255）
```

对应 `AppCore/SYS/config/schema.py` 的 `OverlaySettings`。

## 5. 预览页

`Apps/overlay_preview`（左侧菜单「浮层预览」）共 4 张卡片：

| 卡片 | 内容 |
|------|------|
| 对话框 | 基础（可拖动/可关闭）/ 无标题 / 大尺寸 640 |
| 抽屉 | 左（软件信息）、右（通知）、上（筛选）、下（详情）四个方向，均可拖拽调宽 |
| 确认框 | info / success / warn / error 四种语义 |
| 浮层面板 | 点击按钮展开账户浮层，点外部关闭 |

确认/保存后会弹出 `CToast` 反馈，顺带演示 P0 与 P1 的联动。

## 6. 验收

- `tests/test_overlay_components.py` 共 11 例：对话框居中/接受/ESC/无标题、抽屉右侧与底部几何、
  抽屉限定在内容区且非模态、头部与左抽屉同构、四向贴边、标题/图标可改、确认框信号、
  浮层跟随锚点与开合；
- 深/浅主题分别核对对话框、抽屉、确认框、浮层面板；
- `ruff check` / `ruff format --check` 通过，全量测试保持绿色。
