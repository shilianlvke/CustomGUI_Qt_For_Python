# 反馈与状态组件复刻（P0）

复刻对象：Sakai 的 **Message** 与 **Misc** 两页（<https://sakai.primevue.org/uikit/message>、`/uikit/misc`），
样式依据 `@primeuix/themes` 的 Aura `message` / `tag` / `badge` / `chip` / `avatar` / `skeleton` / `progressbar` / `divider` 预设。

目标：补上“页面能给出反馈、能表达状态”的最小零件集，为后续 Table / List / Tree 打地基。

## 1. 落地内容

| 目录 | 组件 | 能力 |
|------|------|------|
| `GuiCore/CustomUI/feedback/` | `CMessage` | 内联消息：6 种语义色、标题+正文、图标、可关闭、outlined |
| | `CToast` | 浮出通知：右上角堆叠、滑入淡入、定时消失、悬停暂停、同屏上限 |
| `GuiCore/CustomUI/display/` | `CTag` | 实心语义标签，支持图标与胶囊圆角 |
| | `CBadge` | 数字/文字徽标、圆点、可叠加到任意控件右上角 |
| | `CChip` | 胶囊标签片：图标 / 头像 / 可删除 |
| | `CAvatar` | 圆形/方形头像：文字、图标、图片，4 档尺寸 |
| | `CSkeleton` | 骨架屏：矩形 / 圆形 / 文本行，微光扫过 |
| | `CProgressBar` | 确定进度 / 不确定扫描 / 内嵌百分比 |
| | `CDivider` | 水平/垂直分割线，实线/虚线/点线，可带文字并左中右对齐 |

新增 `paint_utils.py`（上移到 `GuiCore/CustomUI/`，`line_edit/paint_utils.py` 保留兼容层），
统一提供勾、叉、箭头、日历、星形路径。

## 2. 关键 API

```python
CMessage(text, title="", severity="info", closable=False, show_icon=True, outlined=False)
#   属性: severity / text / title / is_closable；信号: closed

CToast.show_message(parent, text, title="", severity="info", life=None, offset_top=0) -> CToast
CToast.clear(parent)
#   同窗口自动堆叠；life 为 0 表示不自动消失；offset_top 用于避开标题栏

CTag(text, severity="primary", rounded=False, icon=None)
CBadge(text="", severity="primary", size="md", dot=False)
CBadge.attach(target, text="", severity="danger", size="sm", dot=False)  # 叠加到控件右上角

CChip(text, icon=None, image=None, removable=False)      # 信号: removed
CAvatar(label="", icon=None, image=None, shape="circle", size="md")
CSkeleton(width=120, height=16, shape="rect", animation=True)
CProgressBar(value=0, maximum=100, show_value=False, indeterminate=False, height=6)
CDivider(orientation="horizontal", style="solid", text="", align="center")
```

- `severity` 接受 `Severity` 枚举或字符串，并兼容 PrimeVue 的 `error` / `warning` 别名；
- `CBadge.attach` 会把徽标挂到目标控件的**父容器**上，按目标几何定位，
  这样不会被控件自身裁掉；控件移动/缩放时自动重排。
- `CToast` 的所有实例按窗口分组（`_stacks`），新通知插到最上方，超过上限挤掉最旧的一条。

## 3. 视觉约定

- 颜色一律实时读 `ColorPalette` / `display.palette.tokens()`，切主题后重绘即生效，不缓存色值；
- `CMessage` 用语义色的低透明度底 + 同色描边；`contrast` 是反相卡片（深色主题白底黑字）；
- `CTag` / `CBadge` 用实心语义色 + 自动对比文字色（`contrast_text`）；
- `CSkeleton` 底色跟 `surface_strong`，深色主题用更亮的微光带；
- 所有图形（图标、勾、叉、进度条端点）都是矢量绘制，不新增位图资源。

## 4. 可调参数（`customgui/resource/customui/settings/window.yaml`）

```yaml
feedback:
  toast_life: 3000       # 通知停留时长（毫秒）
  toast_max: 4           # 同屏最多条数
  toast_duration: 180    # 进出动画时长
  toast_margin: 20       # 距窗口边缘
  toast_spacing: 8       # 通知间距
  skeleton_duration: 1400 # 骨架微光一圈时长
```

对应 `AppCore/SYS/config/schema.py` 的 `FeedbackSettings`（带默认值，旧配置不写也能运行）。

## 5. 预览页

`Apps/feedback_preview`（左侧菜单「反馈预览」）共 10 张卡片：

| 卡片 | 内容 |
|------|------|
| 内联消息 | info / success / warn / error / secondary / contrast |
| 消息变体 | outlined ×2、可关闭、自动换行 |
| 浮出通知 | 四个按钮分别弹 success / info / warn / error + 清空 |
| 标签 | 8 种语义色 + 圆角 + 图标 |
| 徽标 | 数字、99+、圆点、lg、叠加在头像与按钮上 |
| 标签片 | 基础 / 图标 / 可删除 |
| 头像 | 文字、图标、方形、xl |
| 骨架屏 | 卡片占位组合 + 静态文本行 |
| 进度条 | 25% / 60% / 80%（带数值）/ 不确定 |
| 分割线 | 实线、虚线、点线、带文字、垂直 |

## 6. 验收

- `tests/test_feedback_components.py` 共 15 例：消息别名与关闭、标签宽度、徽标叠加坐标、
  标签片删除点击、头像尺寸、骨架形状、进度截断与信号、分割线方向、通知堆叠/上限/自动消失/清空；
- 深/浅两套主题截图核对消息、标签、徽标、骨架、进度、分割线与通知；
- `ruff check` / `ruff format --check` 通过，全量测试保持绿色。
