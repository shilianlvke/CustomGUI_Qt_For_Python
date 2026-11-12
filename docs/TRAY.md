# 基座托盘协议

> 状态：`base-v2.2.0` 起生效
>
> 一句话：托盘是**基座常驻能力**。插件只能往菜单里加文本动作、发送系统通知，
> 不能修改图标/悬停提示，也不能介入托盘的创建与销毁。

## 1. 常驻模型

- `GalleryRuntime.bootstrap()` 在插件加载后立即创建并显示全进程唯一的
  `QSystemTrayIcon`，不依赖任何插件是否使用托盘。
- 关闭主窗口（非强制退出）时窗口隐藏、运行时继续；插件与桌面小部件不受影响。
- 「显示主窗口」「退出」是基座固定菜单项，始终位于插件动作之后。
- 插件重载（安装/更新/启停）只重建菜单动作，**不会销毁托盘**；应用退出时
  才 `dispose()`。
- 系统托盘不可用（无桌面环境 / offscreen）时：托盘 API 安全降级为空操作，
  只告警一次；此时关闭主窗口直接退出。

## 2. 所有权矩阵

| 项 | 归属 | 插件能否修改 |
| --- | --- | --- |
| 托盘图标 | 基座 | **禁止**（无 API） |
| 悬停提示 | 基座（语言表 `custom_ui.sys_name`） | **禁止**（无 API） |
| 菜单外壳、「显示主窗口」「退出」 | 基座 | **禁止** |
| 菜单动作（文本 + 回调） | 插件 | 允许（需 `tray` 权限） |
| 系统通知 | 插件 | 允许（需 `notifications` 权限） |
| 创建 / 销毁 / 显示 / 隐藏托盘 | 基座 | **禁止** |

图标固定取 `QApplication.windowIcon()`（基座品牌图标）；应用图标缺失时回落到
内置 `images/ico/icon.ico`，并回填为应用图标。插件自身不需要、也不应该提供
托盘图标资源。

## 3. 公开 API

```python
class GalleryTray(ABC):
    def available(self) -> bool: ...
    def add_action(
        self, action_id: str, text: str, callback: Callable[[], None], *, order: int = 100
    ) -> None: ...
    def set_action_text(self, action_id: str, text: str) -> None: ...
    def remove_action(self, action_id: str) -> None: ...
    def show_message(
        self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000
    ) -> bool: ...
    def clear(self) -> None: ...
```

约束：

- `action_id` 只在插件内唯一，基座自动加 `plugin_id:` 前缀，插件之间互不影响。
- 动作只支持**纯文本 + 回调**：不支持图标、勾选态、二级子菜单；复杂交互放在
  Surface 页面里。
- 排序键为 `(order, action_id)`，`order` 越小越靠前；基座固定项永远在最后。
- 回调在 Qt 主线程执行；基座会隔离异常，单个动作失败不会打断事件循环。
- `add_action` 会同时把托盘置为可见（幂等），插件不需要关心可见性。

## 4. 权限边界

| 权限 | 能力 | 未声明时 |
| --- | --- | --- |
| `tray` | 访问 `ctx.tray`、注册/改文案/移除动作 | 访问 `ctx.tray` 抛 `PLUGIN_PERMISSION_DENIED` |
| `notifications` | `show_message()` | 调用时抛 `PLUGIN_PERMISSION_DENIED` |

- 图标与提示没有对应权限，因为它们根本没有插件 API：这是**结构性禁止**，
  而不是运行期校验。
- 权限是安装前的知情同意，不是沙箱；插件仍以当前用户权限运行。
- 清单 `permissions` 必须与实际调用一致；官方源条目中的 `permissions` 必须与
  清单完全一致（校验器会逐版本比对）。

## 5. 生命周期

```text
应用启动
  └─ GalleryRuntime.bootstrap
       ├─ 加载插件（on_load 可 add_action）
       └─ tray.ensure_visible()            # 无论插件是否使用，托盘常驻
插件运行
  ├─ 动作回调（Qt 主线程，异常被隔离）
  ├─ on_locale_changed → set_action_text # 插件自己刷新动作文案
  └─ 语言切换 → 基座 refresh_texts       # 外壳文案 + 悬停提示
插件重载 / 卸载
  ├─ 加载器调用 ctx.clear_tray()          # 移除该插件全部动作
  └─ 托盘对象保留（重载不销毁，避免图标闪烁）
应用退出
  └─ GalleryRuntime.shutdown → tray.dispose()
```

- `ctx.clear_tray()` 由加载器在 `on_unload` 后调用；插件无需手动清理，但可以
  在 `on_unload` 里主动 `clear()`。
- 插件动作在 `on_load` 之前不存在，`on_unload` 之后不残留。

## 6. 视觉一致性（硬约束）

1. 图标只能是基座品牌图标，插件不得传入路径或替换像素。
2. 悬停提示只能是基座应用名，随语言切换自动更新。
3. 菜单项样式由基座决定：插件动作是普通文本项，不带图标/子菜单/自定义控件。
4. 固定顺序：插件动作（按 order）→ 分隔线 → 显示主窗口 → 退出。
5. 通知走系统原生 `QSystemTrayIcon.showMessage`，不提供通知中心历史。

## 7. 一致性校验点

发布插件或升级基座时逐项确认：

| # | 校验点 | 方式 |
| --- | --- | --- |
| 1 | 插件清单 `requires.sllkgui` 不低于 `2.2.0` | 人工检查 / `sllkgui plugin lint` |
| 2 | 代码中不存在 `tray.set_icon(` / `tray.set_tooltip(` | `rg "tray\.set_(icon\|tooltip)\("` 应为空 |
| 3 | 使用托盘动作时声明 `tray`；使用通知时声明 `notifications` | 清单 vs 代码调用 |
| 4 | 源条目每个版本的 `permissions` 与清单一致 | `python scripts/validate_source.py --clone` |
| 5 | 插件动作文案支持四语言，并在 `on_locale_changed` 刷新 | 切语言后检查菜单 |
| 6 | 加载后动作存在、卸载后动作清零 | 插件冒烟测试断言 `action_count(plugin_id)` |
| 7 | 基座图标来自应用图标而非插件资源 | 启动后检查托盘图标 / `QApplication.windowIcon()` |
| 8 | 关窗隐藏到托盘、托盘「退出」真正退出 | 手工或窗口测试 |

## 8. 兼容性

- `2.2.0` 移除了 `GalleryTray.set_icon()` 与 `set_tooltip()`，属于破坏性变更；
  仍调用它们的插件会在运行期抛 `AttributeError`，必须按本协议删除调用并把
  清单下限提到 `>=2.2.0`。
- 参考实现：py-rm `1.2.0`（只注册动作与通知，图标/提示完全交给基座）。
- 更早的 `2.1.x` 仍允许插件替换图标，官方源不再接受依赖该行为的新版本。

## 9. 后续规划

| 项 | 说明 |
| --- | --- |
| 动作分组 | 按插件分组显示子菜单，标题走统一本地化 |
| 动作状态 | 支持禁用态与勾选态（仍不开放图标） |
| 无托盘降级 | 无系统托盘时把插件动作镜像到主窗口菜单 |
