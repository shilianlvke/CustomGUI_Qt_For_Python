# 基座快捷键协议

> 状态：`base-v2.3.0` 起生效
>
> 一句话：快捷键是**基座统一持有**的输入能力。插件与内置功能注册到同一张表，
> 由基座按「作用域 → 优先级 → 冲突策略」裁决，插件既不能绕过，也不能改写内置项。

## 1. 为什么不用 `QShortcut`

Qt 对同一序列的多个 `QShortcut` 只会触发 `activatedAmbiguously`：既无法表达
优先级，也无法按作用域裁决，更无法在「插件与内置项撞车」时给出确定性结果。

基座改为在 `QApplication` 上安装**唯一**事件过滤器（`ShortcutRegistry`）：

- 按键在送达焦点控件**之前**被统一匹配，命中即 `accept()` 消费；
- 未命中时原样放行，不改变任何既有键盘行为；
- 单条条目只是一个 ``(key, modifiers, callback)``，无额外 QObject，清理成本恒定。

## 2. 作用域

| 作用域 | 生效范围 | 典型用途 |
| --- | --- | --- |
| `global`（默认） | 整个应用：主窗口、浮层、对话框（受模态规则约束） | 打开搜索、切换主题、保存 |
| `local` | 仅宿主控件（`host`）子树内 | 某个页面自己的编辑动作 |

- `local` 必须提供 `host`（通常是 Surface 页面的根控件）；宿主销毁时条目自动注销。
- 两个分别挂在**不同窗口**上的 `local` 快捷键不算冲突：同一个按键事件不可能
  同时落到两棵子树里。

## 3. 平台修饰键

绑定串一律用**可移植文本**书写，同一份配置在 Windows / macOS / Linux 语义一致：

| 语义 | Windows / Linux | macOS | 说明 |
| --- | --- | --- | --- |
| `primary` | Ctrl | ⌘ | 应用主修饰键，**推荐使用** |
| `ctrl` | Ctrl | ⌃（物理 Control） | 物理键语义，不随平台改义 |
| `meta` | Win 键 | ⌘ | 系统键语义 |
| `alt` / `option` | Alt | ⌥ | — |
| `shift` | Shift | ⇧ | — |

改名/别名：`cmd`、`command`、`super`、`win`、`windows`、`os` 均等价于 `meta`；
`control` 等价于 `ctrl`；`opt` 等价于 `alt`。

Qt 在 macOS 上把 ⌘ 映射为 `ControlModifier`、把物理 Control 映射为
`MetaModifier`，解析层已做折算，注册与匹配只比较 Qt 规范位，因此：

- `primary+k` 在 macOS 显示 `⌘K`，在 Windows 显示 `Ctrl+K`；
- `ctrl+k` 在 macOS 是**物理 Control**，与 `primary+k` 是两个不同的绑定。

按键名支持：`a`–`z`、`0`–`9`、`f1`–`f35`、`escape`/`esc`、`enter`/`return`、
`tab`、`space`、`backspace`、`delete`、`insert`、`home`、`end`、`pageup`、
`pagedown`、方向键、`comma`、`period`、`slash`、`backslash`、`semicolon`、
`apostrophe`、`bracketleft`、`bracketright`、`minus`、`equal`、`quoteleft`、
`plus` 等（也可直接写 `,` `.` `/` `;` `'` `[` `]` `-` `=` `` ` ``）。

## 4. 优先级与冲突

| 优先级常量 | 值 | 使用者 |
| --- | --- | --- |
| `PRIORITY_BASE` | 900 | 基座内置（`locked=True`） |
| `PRIORITY_NORMAL` | 500 | 插件默认 |
| `PRIORITY_LOW` | 100 | 插件显式降低（兜底动作） |

派发时在同一次按键命中的条目里按 `(priority, 注册先后)` 取最高一条。

注册时若序列已被占用，按 `conflict` 策略处理：

| 策略 | 行为 |
| --- | --- |
| `error`（默认） | 拒绝注册并抛 `PLUGIN_SHORTCUT_CONFLICT`，**不留下任何条目** |
| `shadow` | 允许共存；优先级更高者生效，高优先级项被禁用后低优先级项接管 |
| `replace` | 顶掉冲突项；冲突项 `locked` 时抛 `PLUGIN_SHORTCUT_LOCKED` |

硬约束：

1. 内置项 `locked=True` 且优先级最高，插件**无法覆盖**（`replace` 也不行）。
2. 插件默认策略是 `error`：撞上内置项时立即得到明确错误码，而不是静默失效。
3. 冲突会写入遥测 `shortcut.conflict` / `shortcut.shadowed` / `shortcut.replaced`，
   便于排查「为什么没生效」。

## 5. 公开 API

```python
class GalleryShortcuts(ABC):
    def available(self) -> bool: ...
    def register(
        self, shortcut_id: str, sequence: str, callback: Callable[[], None], *,
        scope: str = "global",          # "global" | "local"
        priority: int | None = None,    # 默认 PRIORITY_NORMAL
        description: str = "",          # 供设置页/诊断展示
        allow_in_modal: bool = False,   # 模态对话框打开时是否仍生效
        conflict: str = "error",        # "error" | "shadow" | "replace"
    ) -> GalleryShortcut: ...
    def update(self, shortcut_id: str, *, sequence=None, description=None,
               priority=None, enabled=None) -> bool: ...
    def set_enabled(self, shortcut_id: str, enabled: bool) -> bool: ...
    def unregister(self, shortcut_id: str) -> bool: ...
    def bindings(self) -> tuple[ShortcutBinding, ...]: ...
    def conflicts(self) -> tuple[ShortcutConflict, ...]: ...
    def clear(self) -> None: ...

class GalleryShortcut(ABC):
    shortcut_id: str
    sequence: str        # 可移植文本，如 primary+shift+p
    display: str         # 展示文本，如 Ctrl+Shift+P / ⇧⌘P
    enabled: bool
    def set_enabled(self, enabled: bool) -> None: ...
    def update(self, *, sequence=None, description=None, priority=None, enabled=None) -> bool: ...
    def unregister(self) -> None: ...
```

`ShortcutBinding` 字段：`shortcut_id`、`sequence`、`display`、`scope`、
`priority`、`enabled`、`plugin_id`、`description`、`locked`。
`ShortcutConflict` 字段：`sequence`、`shortcut_ids`、`owners`、`winner`。

约束：

- `shortcut_id` 只在插件内唯一，基座自动加 `plugin_id:` 前缀；同 id 重复注册即覆盖。
- 回调在 Qt 主线程执行，基座隔离异常，单个动作失败不会打断事件循环。
- 文本输入框（`QLineEdit` / `QTextEdit` / `QPlainTextEdit` / 数字框 / 键序列编辑器）
  聚焦时，**不含 Ctrl/Alt/Meta 的绑定不会触发**，避免抢走正常输入；带命令修饰键
  的绑定照常生效。
- 长按自动重复不会重复触发（避免切换类动作被连点）。
- 模态对话框打开时默认全部静默，确需穿透请显式 `allow_in_modal=True`。

## 6. 权限边界

| 权限 | 能力 | 未声明时 |
| --- | --- | --- |
| `shortcuts` | 访问 `ctx.shortcuts`、注册/更新/注销快捷键 | 访问 `ctx.shortcuts` 或调用任何方法抛 `PLUGIN_PERMISSION_DENIED` |

- 权限是安装前的知情同意，不是沙箱；插件仍以当前用户权限运行。
- 内置快捷键没有对应权限：它们不由插件注册，也不接受插件修改（结构性隔离）。
- 错误码：`PLUGIN_SHORTCUT_CONFLICT`（序列被占）、`PLUGIN_SHORTCUT_LOCKED`
  （撞上锁定项）、`PLUGIN_SHORTCUT_INVALID`（序列非法 / id 为空）。

## 7. 生命周期

```text
应用启动
  └─ GalleryRuntime.bootstrap
       ├─ 加载插件（on_load 可 ctx.shortcuts.register）
       └─ 快捷键表 install()              # 无论是否有插件使用都装配
窗口创建
  └─ GalleryWindow → install_builtin_shortcuts
       ├─ base.search    primary+k
       └─ base.settings  primary+,
插件运行
  ├─ 按键 → 事件过滤器 → 作用域过滤 → 优先级裁决 → 回调（异常被隔离）
  ├─ Entry.set_enabled / registry.set_active   # 单条 / 全局开关
  └─ 宿主控件 destroyed → 局部条目自动注销
插件重载 / 卸载
  ├─ 加载器调用 ctx.clear_shortcuts()          # 条目与回调一起释放
  └─ 注册表对象保留（重载不重新装配过滤器）
应用退出
  └─ GalleryRuntime.shutdown → registry.shutdown()   # 摘过滤器 + 清空条目
```

- 插件在 `on_unload` 里也可以主动 `ctx.shortcuts.clear()`，但**不需要**：加载器
  在钩子之后统一清理。
- 条目在 `on_load` 之前不存在，`on_unload` 之后不残留。

## 8. 内置快捷键

| id | 序列 | 动作 |
| --- | --- | --- |
| `base.search` | `primary+k` | 打开标题栏搜索弹层（页面快速跳转） |
| `base.settings` | `primary+,` | 打开/收起右侧设置抽屉 |

内置项 `owner="sllkgui.base"`、`priority=PRIORITY_BASE`、`locked=True`，
绑定在宿主窗口上；窗口重建时先注销旧条目再注册，不会堆叠。

## 9. 范围边界

- `global` 是**应用内**全局：窗口失焦到其他应用时不生效，也不会注册系统级热键
  （不抢占其他程序的按键）。需要「后台也生效」的热键必须走原生 API
  （Windows `RegisterHotKey` / macOS Event Tap），不在本协议范围。
- 快捷键不参与输入法候选与 `QKeySequenceEdit` 录制；录制控件会正常收到按键。
- 同一序列在「不同窗口的 local」之间可以共存，这是特性而非漏洞：它们不会同时
  抢同一次按键。

## 10. 一致性校验点
| # | 校验点 | 方式 |
| --- | --- | --- |
| 1 | 使用 `ctx.shortcuts` 的插件声明了 `shortcuts` 权限 | `sllkgui plugin lint`（`SHORTCUTS` 告警） |
| 2 | 序列用 `primary` 而不是硬编码 `ctrl` / `cmd` | 代码评审 / `rg "ctx\.shortcuts\.register"` |
| 3 | 插件不与内置项撞序列 | 注册期抛 `PLUGIN_SHORTCUT_CONFLICT`，启动日志可见 |
| 4 | 卸载后 `registry.count(plugin_id) == 0` | 插件冒烟测试 |
| 5 | 语言切换后 `description` 已刷新 | `on_locale_changed` 里 `handle.update(description=...)` |
| 6 | 编辑框内输入不被抢键 | 手工：在搜索框/输入框里正常输入 |

## 11. 兼容性

- `2.3.0` 新增 `Permission.SHORTCUTS` 与 `GalleryContext.shortcuts`，属于向后兼容
  的增量：未声明 `shortcuts` 的插件行为完全不变（访问 `ctx.shortcuts` 会抛
  `PLUGIN_PERMISSION_DENIED`）。
- 内置快捷键（`primary+k` / `primary+,`）是新增行为；使用这两个组合的插件页面
  需要在清单里声明 `shortcuts` 并改用其他序列。
- 旧宿主若绕开 `GalleryRuntime` 自行构造 `GalleryContextImpl` 且未注入快捷键表，
  `ctx.shortcuts` 抛 `PLUGIN_PERMISSION_DENIED`（与无托盘环境一致）。
