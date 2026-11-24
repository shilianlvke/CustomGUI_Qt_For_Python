# 桌面宠物事件协议

桌面宠物提供统一的发布/订阅事件总线，让基座与插件通过事件控制宠物行为，
而不必直接持有 `MihoutaoPetController` 引用。

## 设计目标

- 解耦：命令发起方只依赖事件主题与载荷，不依赖宠物实例；
- 同构：范式沿用插件事件总线（owner 隔离 + 锁外回调 + 异常隔离），行为可预测；
- 可扩展：新增事件只需在常量表登记，未知载荷键原样透传。

## 命名规范

主题形如 `pet.<域>.<动作>`，全小写、点号分隔：

| 前缀 | 含义 | 发布方 | 订阅方 |
| --- | --- | --- | --- |
| `pet.command.*` | 行为命令 | 基座 / 任意插件 | 宠物控制器 |
| `pet.event.*` | 状态/响应通知 | 宠物控制器 | 基座 / 任意插件 |

只有登记在 `sllkgui.guicore.pet.events.EVENT_TYPES` 中的类型才会被分发；
发布或订阅未登记类型会被拒绝并记录告警，不会抛异常。

## 载荷格式

载荷是 `Mapping[str, Any]`，总线强制注入两个字段：

- `from`：发布者 owner（插件为 plugin_id，基座为 `sllkgui.base`）；
- `seq`：进程内单调递增的序号，用于排查时序。

回调统一收到 `(topic: str, payload: dict)`。命令类事件自带必需载荷键，缺少时发布被拒；
未知键保留透传，便于后续扩展而不破坏旧订阅者。

## 常用行为事件

### 命令（pet.command.*）

| 主题 | 必需载荷 | 效果 |
| --- | --- | --- |
| `pet.command.show` | — | 显示宠物 |
| `pet.command.hide` | — | 隐藏宠物 |
| `pet.command.toggle` | — | 显隐切换 |
| `pet.command.spin` | — | 转一圈 |
| `pet.command.hop` | — | 跳一下 |
| `pet.command.burst` | — | 粒子特效 |
| `pet.command.state` | `state` | 切换情绪状态（须为 39 态之一） |
| `pet.command.shape` | `shape` | 切换果形（须为 18 果形之一） |
| `pet.command.color` | `color` | 切换果肉色（须为 11 色之一） |
| `pet.command.setting` | `key`, `value` | 修改一个宠物配置项 |
| `pet.command.react` | `state`（+ 可选 `hold_ms` / `hold`） | **瞬态**情绪反应，到期自动回到操作前的常态 |

### 状态通知（pet.event.*）

| 主题 | 载荷 | 时机 |
| --- | --- | --- |
| `pet.event.ready` | `visible` | 宠物启动完成 |
| `pet.event.state_changed` | `state` | 情绪状态切换成功 |
| `pet.event.shape_changed` | `shape` | 果形切换成功 |
| `pet.event.color_changed` | `color` | 果肉色切换成功 |
| `pet.event.setting_changed` | `key`, `value` | 配置项变化 |
| `pet.event.visibility_changed` | `visible` | 显隐变化（`show` / `hide` / `toggle` 实际生效时） |

### `state`（保持）与 `react`（瞬态）的区别

这两个命令都能切情绪，但生命周期完全不同，选错会让宠物"卡住"：

| 命令 | 语义 | 适用场景 |
| --- | --- | --- |
| `pet.command.state` | **保持**：一直停在该情绪，直到下次显式切换 | 用户在宠物右键菜单里选情绪 |
| `pet.command.react` | **瞬态**：`hold_ms` 后自动回到反应前的常态 | 基座/插件的操作反馈 |

`react` 的载荷规则：

- `state`：必填，须为 39 个情绪之一；非法值时命令被忽略（与 `state` 一致）；
- `hold_ms`：可选，默认 1600 毫秒；`<= 0` 表示"保持"（不自动到期）；
- `hold`：可选布尔；`true` 等价于 `hold_ms <= 0`，用于设置窗口打开这类有明确
  起止的场景——打开时 `react(state, hold=True)`，关闭时再发一次普通 `react` 解除；
- 额外键（如 `action` / `plugin` / `theme`）原样透传，便于订阅方做二次联动。

`react` 期间再次发布只延长到期时间，**不会覆盖**常态快照；因此连续操作
（搜索 → 切页 → 装插件）结束后宠物一定回到操作前的那个情绪。

## 发布 / 订阅 / 解绑规则

```python
from sllkgui.guicore.pet.events import CMD_SPIN, EVT_STATE_CHANGED, pet_bus

events = pet_bus().handle("com.example.my_plugin")

def on_state(topic, payload):
    print(payload["state"], payload["from"], payload["seq"])

unsubscribe = events.subscribe(EVT_STATE_CHANGED, on_state)
events.publish(CMD_SPIN)                       # 让宠物转一圈
unsubscribe()                                   # 幂等，调用多次安全
events.clear()                                  # 注销本 owner 全部订阅
```

规则：

- `subscribe(topic, callback)` 返回幂等退订闭包；重复退订无副作用；
- `publish(topic, payload)` 返回 `bool`，未登记类型或缺必需载荷返回 `False`；
- 回调在锁外按订阅顺序同步执行，回调内可安全地增删订阅；
- 单个订阅者抛异常只记录告警并继续分发给其它订阅者；
- `clear_owner(owner)` 只清指定 owner 的订阅，插件卸载时由加载器/宿主调用；
- 控制器在 `shutdown()` 中退订全部命令订阅并清空句柄，保证生命周期一致。

## 作用范围与可见性

- 进程内总线，不跨进程；与插件事件总线一样不做网络或沙箱边界；
- owner 隔离仅用于订阅归属与批量清理，不限制谁能发布某主题；
- 命令由宠物控制器独占消费；状态通知对外广播，任何 owner 都可订阅。

## 错误处理

- 未登记主题：发布/订阅被拒，告警并返回 `False` / 空退订闭包；
- 缺少必需载荷：发布被拒并返回 `False`，不分发；
- 无效载荷值（如不存在的 state）：事件正常分发，控制器忽略该命令；
- 订阅者异常：隔离并记录，不影响发布方与其它订阅者；
- 宠物未启动：命令发布成功但无人订阅，属于正常空操作。

## 扩展机制

新增事件类型只需三步：

1. 在 `events.py` 增加 `CMD_*` / `EVT_*` 常量并加入 `EVENT_TYPES`；
2. 若为命令且需必填字段，在 `REQUIRED_PAYLOAD` 登记；
3. 在控制器 `_on_command` 增加分支，或由订阅方处理新 `EVT_*`；
4. 若是基座操作的新联动点，在 `pet_bridge.py` 加 `on_*` 函数并**在真实调用点接线**——
   只加函数不接线等于没接（这正是历史上联动失效的原因：函数存在但无人调用）。

未知载荷键始终透传，因此为现有事件增加可选字段无需修改协议版本。

## 基座操作联动

基座通过 `guis/windows/main_window/pet_bridge.py` 把用户操作按协议发布为宠物命令。
**基座操作一律走 `CMD_REACT`（瞬态）**，因此每次操作结束后宠物都会回到操作前的
常态，不会被最后一次操作永久钉住。

### 已接入的联动点

| 基座操作 | 触发位置 | 宠物反应 |
| --- | --- | --- |
| 主题循环切换 | `SettingsController.cycle_theme` | 跳一下 + 短暂 `happy` |
| 设置窗口保存主题 | `SettingsController._apply_saved_settings` | 转一圈 + 短暂 `happy` |
| 打开设置窗口 | `SettingsController.open_settings_window` | `curious`（保持到关闭） |
| 关闭设置窗口 | `SettingsController._on_settings_window_closed` | 解除保持，回到常态 |
| 打开搜索（按钮 / 快捷键） | `MainWindowController._handle_search_button` | `searching` |
| 收起搜索面板 | `CSearchPalette.closed` | 回到常态（命中跳转时不覆盖切页反馈） |
| 切换页面 | `PageRouterController.switch_page` | 短暂 `curious` |
| 菜单 / 抽屉布局模式变化 | `SettingsController._apply_saved_settings` | 转一圈 |
| 切换界面语言 | `SettingsController._apply_saved_settings` | 短暂 `humming` |
| 主窗口收进托盘 | `GalleryWindow.closeEvent` | 短暂 `drowsy` |
| 主窗口从托盘恢复 | `GalleryWindow.showEvent` | 短暂 `waking` |
| 退出应用 | `GalleryWindow.quit_application` | `powering-down` |
| 插件安装 / 更新 / 回滚 / 卸载 / 启停 | `StorePage` 各动作 | 见下表 |
| 插件来源添加 / 移除 / 刷新、列表刷新 | `StorePage` 各动作 | 见下表 |
| 插件重载 | `StorePage._reload_one` | `loading` → `happy` / `sad` |

### 插件管理操作的反馈

`StorePage` 通过 `_pet_operation_started(action)` / `_pet_operation(action, ok=...)`
发布反馈；映射表见 `pet_bridge.PLUGIN_OPERATION_REACTIONS`：

| 动作 | 开始 | 成功 | 失败 |
| --- | --- | --- | --- |
| `install` | `loading` | `celebrate` + 粒子 | `sad` |
| `update` | `uploading` | `celebrate` + 粒子 | `sad` |
| `rollback` | `loading` | `waking` + 粒子 | `sad` |
| `remove` | `powering-down` | `proud` + 粒子 | `sad` |
| `enable` | `thinking` | `excited` + 粒子 | `sad` |
| `disable` | `thinking` | `drowsy` + 粒子 | `sad` |
| `source-add` | `loading` | `spawning` + 粒子 | `sad` |
| `source-remove` | `working` | `powering-down` + 粒子 | `sad` |
| `source-refresh` | `radar` | `listening` + 粒子 | `sad` |
| `refresh` | `listening` | `listening` + 粒子 | `sad` |
| `reload` | `loading` | `happy` + 粒子 | `sad` |
| 未登记动作 | — | `working` + 粒子 | `sad` |

**只有成功才放粒子**：失败时同时撒花会让错误提示显得不可信；未登记动作走兜底
反应时同样按成功/失败区分。
未登记的动作走 `FALLBACK_PLUGIN_REACTION`，所以新增操作不会静默无反馈。

事件桥只负责发布，不直接持有宠物控制器；总线或宠物未就绪时静默降级，绝不打断基座操作。

### 无法联动的操作

以下操作没有接入，原因都属于"没有对应的用户可感知瞬间"或"没有可表达的宠物语义"：

| 操作 | 原因 |
| --- | --- |
| 窗口拖拽 / 缩放 | 每次鼠标移动都会触发，逐帧发布会淹没事件总线，且宠物已有跟随指针能力 |
| 抽屉/列的开合动画 | 纯布局过渡，无用户语义终点；模式切换已由布局模式联动覆盖 |
| 滚动、悬停、焦点变化 | 高频且无操作语义，宠物无可对应情绪 |
| 设置项实时预览（未保存） | 预览会被反复撤销，宠物反馈会闪烁；只在保存时反馈 |
| 插件管理页的搜索/过滤输入 | 与基座搜索弹层语义重叠，且逐键触发过于频繁 |
| CLI 子命令（`plugin install` 等） | 不经过 GUI 进程，宠物未启动；总线是进程内的 |
| 系统托盘菜单的插件动作 | 回调由插件自己定义，基座不解释语义；插件可自行发布 `CMD_REACT` |
| 插件内部操作（页面内按钮等） | 属于插件自己的 UI，基座不拦截；插件经 `pet_bus()` 自行联动 |

## 与基座 / 插件机制的关系

- 总线实例由 `pet_bus()` 进程级惰性提供，测试用 `reset_pet_bus()` 隔离；
- 插件通过现有 `ctx.events` 是插件间总线；要控制宠物请改用 `pet_bus()`，
  两者职责不同：前者随 runtime 生命周期，后者随宠物进程级常驻；
- 遥测仍走 `record_event`，事件总线只负责命令与状态分发。
