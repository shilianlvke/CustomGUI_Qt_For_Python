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

### 状态通知（pet.event.*）

| 主题 | 载荷 | 时机 |
| --- | --- | --- |
| `pet.event.ready` | `visible` | 宠物启动完成 |
| `pet.event.state_changed` | `state` | 情绪状态切换成功 |
| `pet.event.shape_changed` | `shape` | 果形切换成功 |
| `pet.event.color_changed` | `color` | 果肉色切换成功 |
| `pet.event.setting_changed` | `key`, `value` | 配置项变化 |
| `pet.event.visibility_changed` | `visible` | 显隐变化 |

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
3. 在控制器 `_on_command` 增加分支，或由订阅方处理新 `EVT_*`。

未知载荷键始终透传，因此为现有事件增加可选字段无需修改协议版本。

## 与基座 / 插件机制的关系

- 总线实例由 `pet_bus()` 进程级惰性提供，测试用 `reset_pet_bus()` 隔离；
- 插件通过现有 `ctx.events` 是插件间总线；要控制宠物请改用 `pet_bus()`，
  两者职责不同：前者随 runtime 生命周期，后者随宠物进程级常驻；
- 遥测仍走 `record_event`，事件总线只负责命令与状态分发。
