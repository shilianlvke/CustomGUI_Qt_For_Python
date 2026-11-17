# 基座托盘协议

> 状态：`base-v2.4.0` 起生效（`2.2.0` 起托盘常驻，`2.4.0` 起分组与预算）
>
> 原型：[docs/prototype/tray-menu.html](prototype/tray-menu.html)（可切换三种结构方案与插件规模）
>
> 一句话：托盘是**基座常驻能力**。插件只声明「这条动作属于哪个槽、排多前」，
> 菜单里长什么样（内联 / 子菜单 / 兜底桶）由基座按槽预算裁决；图标、提示、
> 外壳与生命周期全部由基座独占。

## 1. 常驻模型

- `GalleryRuntime.bootstrap()` 在插件加载后立即创建并显示全进程唯一的
  `QSystemTrayIcon`，不依赖任何插件是否使用托盘。
- 关闭主窗口（非强制退出）时窗口隐藏、运行时继续；插件与桌面小部件不受影响。
- 基座固定项（显示主窗口 / 设置… / 退出）永远在最后一段，插件无法插入其后。
- 插件重载（安装/更新/启停）只重建菜单动作，**不会销毁托盘**；应用退出时
  才 `dispose()`。
- 系统托盘不可用（无桌面环境 / offscreen）时：托盘 API 安全降级为空操作，
  只告警一次；此时关闭主窗口直接退出。

## 2. 所有权矩阵

| 项 | 归属 | 插件能否修改 |
| --- | --- | --- |
| 托盘图标 | 基座 | **禁止**（无 API） |
| 悬停提示 | 基座（语言表 `custom_ui.sys_name`） | **禁止**（无 API） |
| 菜单外壳与基座固定项 | 基座 | **禁止** |
| 槽目录（quick / tools / status）与预算 | 基座 | **禁止**（只能引用） |
| 菜单动作（文案 + 槽 + 次序 + 回调） | 插件 | 允许（需 `tray` 权限） |
| 动作形态（内联 / 子菜单 / 兜底桶） | 基座 | **禁止**（只能通过 `submenu` 表达偏好） |
| 系统通知 | 插件 | 允许（需 `notifications` 权限） |
| 创建 / 销毁 / 显示 / 隐藏托盘 | 基座 | **禁止** |

图标固定取 `QApplication.windowIcon()`（基座品牌图标）；应用图标缺失时回落到
内置 `images/ico/icon.ico`，并回填为应用图标。插件自身不需要、也不应该提供
托盘图标资源。

## 3. 三层模型

```text
主菜单
├─ 槽 quick      内联直达，每插件至多 1 条
├─ 槽 tools      默认槽，按插件分块：独占内联 / 多块子菜单
├─ 槽 status     只读状态，恒为禁用态
├──────────────  基座分隔线（插件不可跨越）
└─ 基座区        显示主窗口 / 设置… / 退出
```

- **槽（slot）**：语义分区，次序与预算由基座固定，插件只能选择其一。
- **块（block）**：同一插件在同一槽内的动作集合，标题取插件 `name`。
- **项（action）**：一条文本动作 + 回调。

槽目录**封闭且只增不改**：不认识的槽直接报错（`PLUGIN_TRAY_GROUP_INVALID`），
不做静默回落——插件以为注册成功却出现在别处，比报错更难排查。

## 4. 注册协议

```python
ctx.tray.add_action(
    "start", "开始专注", on_start,   # id 在插件内唯一，重名覆盖
    group="tools",                   # quick | tools | status
    order=10,                        # 槽内次序，越小越靠前
    submenu=None,                    # None 自动 / True 强制 / False 偏好内联
    enabled=True,
)
```

| 字段 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `action_id` | `str` | 必填 | `^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$`，插件内唯一；基座加 `plugin_id:` 前缀 |
| `text` | `str` | 必填 | 1–40 字，去首尾空白；不允许空串 |
| `callback` | `Callable[[], None]` | 必填 | Qt 主线程执行，异常由基座隔离 |
| `group` | `str \| TrayGroup` | `tools` | 仅 `quick` / `tools` / `status`；写 `base` 抛 `PLUGIN_TRAY_GROUP_FORBIDDEN` |
| `order` | `int` | `100` | `0–999`，`bool` 不当作整数 |
| `submenu` | `bool \| None` | `None` | 只表达偏好，见 §5.2 |
| `enabled` | `bool` | `True` | `status` 槽恒为禁用，声明无效 |

- 不做清单级声明：动作文案必须运行时本地化，清单与代码双写必然漂移，
  因此**注册调用是唯一事实来源**。
- `action_id` 只在插件内唯一；跨插件天然隔离，不可能撞车。
- 同一 `action_id` 重复注册 = 覆盖（幂等更新），不报错、不改变槽内位置规则。

## 5. 展示裁决

### 5.1 槽（基座决定）

| 槽 | 形态 | 预算 | 溢出处理 |
| --- | --- | --- | --- |
| `quick` | 恒内联，逐条直达 | 5 条 | 超出的动作降级到 `tools`（仍可见，不丢弃） |
| `tools` | 按插件分块，见 5.2 | 7 行（含兜底桶） | 放不下的块收进「更多插件 ▸」 |
| `status` | 恒内联、恒禁用 | 3 条 | 超出截断，写 `tray_menu.compressed` 级日志 |

### 5.2 块（槽内形态）

| 条件 | 形态 |
| --- | --- |
| 槽内只有 1 个插件块 | **全部内联**（单插件时零层级） |
| 槽内 ≥2 个插件块 | **每块一个以插件名命名的子菜单**（形状统一、归属可辨） |
| 块内任一动作 `submenu=True` | 强制子菜单 |
| 块内**全部**动作 `submenu=False` 且 ≤3 条 | 允许保留内联（作者显式选择，混排由作者负责） |
| 块内动作 >3 条 | 强制子菜单（防止单插件把槽撑爆） |

### 5.3 超屏兜底（三级降级）

1. **配额**：`quick 5` + `tools 7` + `status 3` + 基座 3 = **顶层最多 18 行**
   （≈610px），768p 屏幕可完整展开；单插件动作上限 12 条，超出直接拒绝。
2. **收拢**：`quick` 溢出降级到 `tools`；`tools` 放不下的块进入「更多插件 ▸」，
   桶内**平铺 + `插件名 · 动作` 前缀**，保证菜单层级不超过 2；`status` 溢出截断。
3. **硬兜底**：极端窄屏仍超出时由自绘菜单夹紧高度并滚动（滚轮一次 3 行、
   键盘移动自动滚入视野），基座只保证“高度 ≤ 屏幕可用区域”。

> 预算按「行」而不是按「插件数」计：`tools` 里允许内联的块也计入行数，
> 因此 100 个插件与 10 个插件产生的顶层行数上界相同。

## 6. 排序

逐层给出完整兜底键，任何一层撞车都不需要报错：

| 层 | 排序键 |
| --- | --- |
| 槽 | 固定目录次序：`quick 10` → `tools 20` → `status 30` → 基座 `90` |
| 插件块 | `块内最小 order` → 插件名 → 插件 id（Unicode 码位序，稳定可复现） |
| 槽内动作 | `order` → 文案（casefold） → 完整 `plugin_id:action_id` |
| 基座项 | 固定声明顺序，不受任何插件影响 |

- 同一次序的多个插件块按**插件名**排；中文名按码位序，不是拼音序。
  需要固定相对位置时，请显式给不同 `order`。
- 基座项永远在最后，且与插件区之间有且只有一条分隔线。

## 7. 冲突与拒绝

| 场景 | 处理 | 错误码 |
| --- | --- | --- |
| 同插件同 `action_id` 重复注册 | 覆盖，视为幂等更新 | — |
| 跨插件同 `action_id` | 前缀隔离，不存在冲突 | — |
| 同槽同 `order` | 按文案、再按完整 id 兜底，结果确定 | — |
| 同槽同插件两条动作文案相同 | 允许，但语义重复（lint 建议改写） | — |
| 非法 `action_id` / 空白文案 / 超长文案 / 非法 `order` | 拒绝注册 | `PLUGIN_TRAY_ACTION_INVALID` |
| 未知槽 | 拒绝注册 | `PLUGIN_TRAY_GROUP_INVALID` |
| 写入基座区（`group="base"`） | 拒绝注册 | `PLUGIN_TRAY_GROUP_FORBIDDEN` |
| 单插件动作数 > 12 | 拒绝注册 | `PLUGIN_TRAY_QUOTA_EXCEEDED` |
| 未声明 `tray` 权限 | 访问 `ctx.tray` 或调用任何方法即拒绝 | `PLUGIN_PERMISSION_DENIED` |

拒绝发生在**注册期**而不是渲染期：插件加载失败会被隔离并记录，比菜单里少了
一条动作更容易定位。

## 8. 公开 API

```python
class GalleryTray(ABC):
    def available(self) -> bool: ...
    def add_action(
        self, action_id: str, text: str, callback: Callable[[], None], *,
        order: int = 100,
        group: str | TrayGroup = TrayGroup.TOOLS,
        submenu: bool | None = None,
        enabled: bool = True,
    ) -> None: ...
    def set_action_text(self, action_id: str, text: str) -> None: ...
    def set_action_enabled(self, action_id: str, enabled: bool) -> None: ...
    def remove_action(self, action_id: str) -> None: ...
    def entries(self) -> tuple[TrayEntry, ...]: ...
    def show_message(
        self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000
    ) -> bool: ...
    def clear(self) -> None: ...
```

```python
@dataclass(frozen=True)
class TrayEntry:
    action_id: str        # 插件内短 id
    text: str
    group: str            # 声明的槽
    order: int
    enabled: bool         # 实际生效值（status 恒 False）
    plugin_id: str
    rendered_as: str      # inline | submenu | bucket
    path: tuple[str, ...] # 菜单里的完整路径，如 ("番茄钟", "开始专注")
```

`entries()` 返回**实际落位**而不是声明值：被降级、被收进兜底桶、被强制禁用的
动作都能在这里看出来，插件自检与 `sllkgui plugin lint` 都靠它。

## 9. 权限边界

| 权限 | 能力 | 未声明时 |
| --- | --- | --- |
| `tray` | 访问 `ctx.tray`、注册/改文案/启停/移除动作 | 访问 `ctx.tray` 抛 `PLUGIN_PERMISSION_DENIED` |
| `notifications` | `show_message()` | 调用时抛 `PLUGIN_PERMISSION_DENIED` |

- 图标与提示没有对应权限，因为它们根本没有插件 API：这是**结构性禁止**，
  而不是运行期校验。
- 槽目录、预算与形态裁决同样没有插件入口：插件只能声明语义。
- 权限是安装前的知情同意，不是沙箱；插件仍以当前用户权限运行。
- 清单 `permissions` 必须与实际调用一致；官方源条目中的 `permissions` 必须与
  清单完全一致（校验器会逐版本比对）。

## 10. 生命周期

```text
应用启动
  └─ GalleryRuntime.bootstrap
       ├─ 加载插件（on_load 可 add_action）
       └─ tray.ensure_visible()            # 无论插件是否使用，托盘常驻
插件运行
  ├─ 动作回调（Qt 主线程，异常被隔离）
  ├─ on_locale_changed → set_action_text # 插件自己刷新动作文案
  └─ 语言切换 → 基座 refresh_texts       # 外壳文案 + 悬停提示 + 「更多插件」
插件重载 / 卸载
  ├─ 加载器调用 ctx.clear_tray()          # 移除该插件全部动作
  └─ 托盘对象保留（重载不销毁，避免图标闪烁）
应用退出
  └─ GalleryRuntime.shutdown → tray.dispose()
```

- 菜单在每次注册/更新/移除后重建；单次重建只清空动作，不销毁托盘。
- 插件动作在 `on_load` 之前不存在，`on_unload` 之后不残留。
- 形态是**自适应**的：卸载到只剩一个插件时，该槽自动回到内联形态。

## 11. 视觉一致性（硬约束）

1. 图标只能是基座品牌图标，插件不得传入路径或替换像素。
2. 悬停提示只能是基座应用名，随语言切换自动更新。
3. 菜单项样式由基座决定：插件动作是普通文本项，不带图标、勾选态或自定义控件。
4. 固定顺序：槽 quick → tools → status → 分隔线 → 基座固定项。
5. 通知走系统原生 `QSystemTrayIcon.showMessage`，不提供通知中心历史。
6. 「更多插件」是基座保留文案，插件不得占用同名子菜单。
7. 菜单由基座**自绘**（`CPopupMenu`，不继承 `QMenu`）：颜色、圆角、悬停、
   分隔线、子菜单箭头与贴边翻转都在基座手里，主题切换后重绘即生效。
   `docs/prototype/tray-menu.html` 里的序号（`10 / 20`）与左侧括号属于
   **设计标注层**，实机不显示；圆角、果绿悬停与箭头则与原型一致。
   组件说明见 `docs/POPUP_MENU.md`。

## 12. 一致性校验点

发布插件或升级基座时逐项确认：

| # | 校验点 | 方式 |
| --- | --- | --- |
| 1 | 插件清单 `requires.sllkgui` 不低于 `2.4.0` | 人工检查 / `sllkgui plugin lint` |
| 2 | 代码中不存在 `tray.set_icon(` / `tray.set_tooltip(` | `rg "tray\.set_(icon\|tooltip)\("` 应为空 |
| 3 | 每个动作都显式写了 `group` 与 `order` | 代码评审 |
| 4 | `quick` 槽每插件不超过 1 条，文案为「动词 + 对象」 | `entries()` 断言 `group == "quick"` 的条数 |
| 5 | 单插件动作总数 ≤ 12，`text` ≤ 40 字 | `entries()` 长度断言 |
| 6 | 使用托盘动作时声明 `tray`；使用通知时声明 `notifications` | 清单 vs 代码调用 |
| 7 | 源条目每个版本的 `permissions` 与清单一致 | `python scripts/validate_source.py --clone` |
| 8 | 插件动作文案支持四语言，并在 `on_locale_changed` 刷新 | 切语言后检查菜单 |
| 9 | 加载后动作存在、卸载后动作清零 | 插件冒烟测试断言 `action_count(plugin_id)` |
| 10 | 基座图标来自应用图标而非插件资源 | 启动后检查托盘图标 / `QApplication.windowIcon()` |
| 11 | 关窗隐藏到托盘、托盘「退出」真正退出 | 手工或窗口测试 |

## 13. 兼容性

- `2.4.0` **新增** `group` / `submenu` / `enabled` 字段与 `entries()`，全部带默认值，
  现有插件不需要改代码即可运行。
- 行为变化：多个插件同时注册 `tools` 动作时，各自的动作会收进同名子菜单，
  不再平铺混排——这是本次要修的问题，属于**形态变化而非 API 破坏**。
- `2.2.0` 移除了 `GalleryTray.set_icon()` 与 `set_tooltip()`，属于破坏性变更；
  仍调用它们的插件会在运行期抛 `AttributeError`。
- 参考实现：py-rm `1.2.0`（只注册动作与通知，图标/提示完全交给基座）。

## 14. 后续规划

| 项 | 说明 |
| --- | --- |
| 勾选态 | 展开子菜单内的 `checkable` 动作（仍不开放图标） |
| 托盘管理器 | 设置页展示 `entries()` 结果，让用户看到每条动作的实际落位 |
| 无托盘降级 | 无系统托盘时把插件动作镜像到主窗口菜单 |
