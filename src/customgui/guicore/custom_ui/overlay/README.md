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
| `overlay/drawer.py` | `CDrawer` | 左/右/上/下四向滑入，贴边全高（或全宽） |
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

CDrawer(title="", position="right", size=360, closable=True, dismissable_mask=True, parent=None)
#   content_layout 可继续添加控件；位置支持 left / right / top / bottom

CConfirmDialog(title="Confirm", message="", severity="warn",
               accept_text="Yes", reject_text="No", parent=None)
CConfirmDialog.ask(parent, title, message, severity) -> bool   # 阻塞式

COverlayPanel(target, width=300)
#   set_content(widget) / open_panel() / close_panel() / toggle() / is_open()
#   信号：toggled(bool)
```

- 对话框/抽屉铺满父窗口，绘制半透明遮罩；点击卡片外区域或按 ESC 关闭（可关）；
- 底部按钮默认「拒绝（outlined）+ 接受（primary）」，也可用 `add_footer_button` 追加；
- 需要一次性使用时设置 `dialog.setAttribute(Qt.WA_DeleteOnClose, True)`，关闭后自动销毁；
- `exec_dialog()` 内部用 `QEventLoop` 等待 `accepted / rejected / closed`，不依赖 `QDialog.exec()`。

## 3. 交互与视觉

- 遮罩透明度、动画时长来自 `window.yaml` 的 `overlay` 段；
- 对话框淡入淡出（`dialog_duration`），抽屉滑入滑出（`drawer_duration`）；
- 卡片底色：深色主题 `custom_bg_one`，浅色主题白色；描边取 `display.palette.tokens()`；
- 标题栏可拖动（限制在遮罩范围内），拖动时不会移出窗口；
- 抽屉贴边无圆角，对话框圆角 10px，阴影由遮罩层在卡片下方绘制；
- 对话框正文包在透明滚动区里：不超高时按内容高度自适应，超高时封顶内滚（滚轮可滚），
  正文不再被截断；
- 抽屉可拉伸：贴边内侧有 6px 拖拽热区（left/right 拖宽、top/bottom 拖高），
  悬停显示主色细线，拖动实时重排，尺寸限制在 200 ~ 窗口主轴-80。

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
| 抽屉 | 左、右、上、下四个方向 |
| 确认框 | info / success / warn / error 四种语义 |
| 浮层面板 | 点击按钮展开账户浮层，点外部关闭 |

确认/保存后会弹出 `CToast` 反馈，顺带演示 P0 与 P1 的联动。

## 6. 验收

- `tests/test_overlay_components.py` 共 7 例：对话框居中/接受/ESC/无标题、抽屉右侧与底部几何、
  确认框信号、浮层跟随锚点与开合；
- 深/浅主题分别核对对话框、抽屉、确认框、浮层面板；
- `ruff check` / `ruff format --check` 通过，全量测试保持绿色。
