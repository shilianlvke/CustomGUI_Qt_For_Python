# 统一 Toast 协议（v1）

> **状态：设计稿，尚未实现。** 本文定义协议与接入规范；§8 给出文件级实现落点，
> §9 给出兼容与迁移路径。落地前的现状盘点见
> [reviews/2026-11-22-toast-audit.md](reviews/2026-11-22-toast-audit.md)。
>
> 适用基座：SllkGUI `4.0.x`（插件协议 API 2）。协议自身版本 `TOAST_PROTOCOL_VERSION = 1`。

---

## 0. 一页摘要

| 项 | 结论 |
| --- | --- |
| 唯一入口 | 插件侧 `ctx.toast`；基座原生页侧 `guicore.feedback.toast_bus()` |
| 唯一渲染器 | `CToast`（Windows Fluent InfoBar 风格），协议层不重新实现外观 |
| 类型 | 7 级：`success` `info` `warn` `error` `neutral` `loading` `progress` |
| 返回 | 一律返回 `ToastHandle`，**不抛异常**；失败通过 `handle.result.code` 表达 |
| 默认时长 | success/info 3000、neutral 2000、warn 6000、error 8000、loading/progress 常驻 |
| 去重 | `dedupe_key` + 窗口（默认 1200ms）+ 4 种策略（suppress/restart/count/replace） |
| 队列 | 每个锚点窗口一条栈（上限 `feedback.toast_max`=4）；**无阻塞队列**，溢出按级别裁决 |
| 并发 | 任意线程可调；跨线程自动排队到 GUI 线程；进度更新 100ms 合并 |
| 回调 | `on_dismiss(reason)` / `on_action(id)`；同时发 `toast.shown/updated/dismissed/action` 遥测 |
| 错误码 | `TOAST_*` 19 个稳定码；业务错误码经 `code=` 透传，不进文案 |
| 兼容 | API 2 不升版；`ctx.toast` 以非抽象属性加入，`CToast` 直调保留但降级为内部 API |

---

## 1. 目标、边界与术语

### 1.1 目标

1. **一个入口**：插件不再各自包一层 `_toast` / `_set_status` / 私有浮层，统一走 `ctx.toast`。
2. **一致行为**：时长、堆叠、避让标题栏、去重、跨窗口锚定、语言切换、热重载清理都由基座裁决。
3. **可观测**：每条 toast 有稳定 id、级别、通道与结果码；失败可回放（遥测 + 日志）。
4. **可测试**：协议层可脱离 Qt 事件循环用假渲染器断言；插件测试用记录型宿主即可。
5. **不打断业务**：任何 toast 失败都不得抛出到调用方，不得改变插件控制流。

### 1.2 非目标（明确划界）

| 场景 | 不归属 toast 协议 | 应使用 |
| --- | --- | --- |
| 破坏性操作前的确认 | 需要焦点与阻断 | `CConfirmDialog.ask(...)` / `CConfirmPopup` |
| 表单字段级校验 | 需要就近定位到字段 | 字段下方 `CMessage(simple=True)` 或 `CFormField` 错误位 |
| 常驻状态说明（离线、只读、待授权） | 不是瞬时反馈 | `CMessage` 内联条 / 页脚状态标签 / `CChip` |
| 窗口不在前台时的系统提醒 | 属操作系统通知 | `ctx.tray.show_message(...)`（需 `notifications`/`tray` 权限） |
| 页内长任务进度（页面自带进度区） | 用户正看着该区域 | 页内 `BusyStrip` / `CProgressBar`（toast 仅在离开该页后接管） |
| 需要用户输入或多项选择 | toast 不可聚焦 | `CDialog` / `CConfirmDialog` |

> 边界规则不是"少做"，而是**把 4 类非瞬时反馈显式指派给已有组件**，从而保证
> 任何"要提示用户"的场景都有唯一归属，不出现"协议没覆盖所以各写一套"。

### 1.3 术语

- **锚点（anchor）**：承载 toast 栈的顶层窗口。默认按 `AUTO` 解析，见 §3.2。
- **通道（channel）**：同一语义流的一组 toast，通道内可按 `mode` 替换/合并。
- **作用域（scope）**：去重与限流的隔离单位，插件固定为 `plugin_id`，基座为 `base`。
- **持久（persistent）**：`life=0`，不自动消失，必须由 `resolve`/`dismiss` 收敛。

---

## 2. 现状要点（详情见审计文档）

| 现象 | 代码位置 | 后果 |
| --- | --- | --- |
| 无插件级 toast API | `gallery/api.py` 的 `GalleryContext` 无 `toast` | 三个项目各写一层封装 |
| 四套私有封装 | py-rm `_set_status`、py-listen `_toast` / `_show_toast`、基座 `set_status` | 去重/时长/偏移语义互不相同 |
| 偏移硬编码 | `plugin_store/theme.py:122`、`tools_dialogs.py:60`（`_TOAST_OFFSET = 58`）、py-rm `_toast_offset()` | 标题栏高度变化即错位 |
| 锚点绑页面 | py-rm 以 `self`（页面）为 parent | 切页后 toast 随页面销毁而消失 |
| 未知级别抛错 | `normalize_severity()` 对非枚举值抛 `ValueError` | 插件传 `level="critical"` 会打断业务 |
| 常驻泄漏 | `life=0` 无兜底 | 忘记关闭的 loading 永久停留 |
| 错误码丢失 | `plugin_store/page.py:1163 _fail` 只显示通用文案 | 用户拿不到可定位信息 |

---

## 3. 分层与所有权

### 3.1 三层职责

```text
插件 / 原生页
   │  ctx.toast.show(...)                 ← 协议层（无 Qt，可单测）
   ▼
gallery/toast.py  ToastRouter             ← 作用域、限流、遥测、卸载清理
   │  注入的 host 回调（组合根绑定）
   ▼
guicore/feedback/toast_bus.py  ToastBus   ← 通道、去重、队列、状态机
   │  渲染器适配
   ▼
guicore/custom_ui/feedback/toast.py  CToast  ← 外观、动画、堆叠、悬停暂停
```

| 层 | 文件（新增/修改） | 依赖约束 |
| --- | --- | --- |
| 协议类型 | `gallery/api.py`（新增类型与 `GalleryToast` ABC） | 不 import PySide6（该文件现有约定） |
| 协议实现 | `gallery/toast.py`（新增） | 只依赖 `gallery.api` + `appcore`，Qt 由 host 回调带入 |
| UI 总线 | `guicore/feedback/toast_bus.py`（新增） | 依赖 `appcore` + `guicore`（Qt） |
| 渲染器 | `guicore/custom_ui/feedback/toast.py`（扩展） | 现有组件，保持 `show_message` 兼容 |
| 组合根 | `gallery/window.py`（绑定 host）、`gallery/runtime.py`（持有 router） | `gallery → guis` 仍只允许 `window.py` 这一条边 |

### 3.2 锚点解析（`ToastAnchor`）

| 值 | 解析顺序 |
| --- | --- |
| `AUTO`（默认） | `QApplication.activeModalWidget()` 的顶层窗口 → `activeWindow()` → `ctx.parent_window()` → 主窗口 → 任意可见顶层窗口 |
| `MAIN` | 基座主窗口（`GalleryWindow`） |
| `SETTINGS` | 设置窗口（`CSettingsWindow`），不存在时回落 `MAIN` |

规则：

1. **禁止把页面控件当锚点**。页面会随导航销毁，toast 随之消失（现 py-rm 即如此）。
2. `AUTO` 必须优先命中活动模态窗口：设置窗口里的动作结果应出现在设置窗口，而不是被主窗口遮住。
3. 锚点解析失败（全部窗口已关闭、或处于无显示环境）→ 返回 `TOAST_NO_ANCHOR_WINDOW`，静默降级为日志。
4. 锚点窗口 `closeEvent` 时，其上全部 toast 以 `HOST_CLOSED` 收敛，不残留句柄。

---

## 4. 协议数据模型

### 4.1 类型 `ToastLevel`

| 级别 | 语义 | 图标 | 默认时长 | 常驻 | 旧 `Severity` 等价 |
| --- | --- | --- | --- | --- | --- |
| `success` | 变更已完成（保存/启用/导入成功） | ✓ | 3000 | 否 | `success` |
| `info` | 中性进展或结果（已加入队列） | i | 3000 | 否 | `info` |
| `warn` | 已降级但继续（部分项未转换、配置缺失） | ! | 6000 | 否 | `warn` / `warning` |
| `error` | 操作失败，用户需处理 | × | 8000 | 否 | `danger` / `error` |
| `neutral` | 极轻量确认（已复制、已刷新） | 无图标 | 2000 | 否 | `secondary` |
| `loading` | 进行中，结果未知 | 旋转（P2） | 0 | **是** | 无（现有能力缺口） |
| `progress` | 可量化进度 | 环形/条（P2） | 0 | **是** | 无（现有能力缺口） |

兼容别名（**必须接受，不得抛错**）：

| 传入 | 归一为 | 说明 |
| --- | --- | --- |
| `warning` | `warn` | 现有 `_ALIASES` 已支持 |
| `danger` / `critical` / `fatal` | `error` | `critical` 为新增别名，避免插件按系统日志级别写 |
| `primary` / `help` | `info` | 按钮语义误用为提示级别 |
| `contrast` | `neutral` | 同上 |
| 其它任意字符串 | `info` + 返回 `TOAST_INVALID_LEVEL` | **不抛异常**；首帧一次遥测告警 |

### 4.2 消息内容

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `text` | `str` | 是 | 纯文本；建议 ≤120 字符，硬上限 500（超出截断 + `TOAST_TEXT_TRUNCATED`） |
| `title` | `str` | 否 | ≤32 字符，短标题；为空时只渲染正文 |
| `detail` | `str` | 否 | 技术细节（异常串、路径）。**默认不渲染**，只进日志与 tooltip（P2） |
| `text_key` | `str` | 否 | 插件语言键，仅用于遥测定位与排查；基座不据此重译 |
| `code` | `str` | 否 | 业务/协议错误码；随句柄、事件与 `ToastDismiss` 回传，不渲染 |
| `payload` | `Mapping[str, Any]` | 否 | 透传给回调与遥测；需 JSON 可序列化，≤1 KB，超出部分丢弃 |

规则：

1. **纯文本**：不允许 HTML/富文本；允许 `\n`，渲染器按宽度自动换行，超过 3 行折叠（P2）。
2. **不拼接技术细节**：错误文案写"用户话术"，异常信息放 `detail`。现有 py-listen
   `"解析失败：{error}"` 这类把异常串直接铺在正文的写法，按本协议拆成
   `text` + `detail`。
3. **国际化由调用方完成**：插件用 `ctx.text(...)` 生成 `text`；基座只对自身错误码做本地化（§4.9）。
4. **不放入可执行内容**：不得承载链接、命令、脚本片段。
5. **多语言切换**：已显示的 toast 不重译（瞬时组件），文案在下一次弹出时生效。

### 4.3 状态机 `ToastState`

```text
                    show()
                      │
      ┌───────────────┼───────────────────────────────┐
      │ 命中去重 SUPPRESS                            │ 锚点/宿主不可用
      ▼                                              ▼
   CLOSED(duplicate_of)                        CLOSED(no_anchor)
      │
      ▼
   QUEUED ── 进入 GUI 线程 / 同帧合并 ──► SHOWN ──update()──► SHOWN
                                            │
              ┌──────────┬──────────┬───────┼──────────┬─────────────┐
              ▼          ▼          ▼       ▼          ▼             ▼
          life 到点   dismiss()   被挤出   动作按钮   宿主关闭    插件卸载
              │          │          │       │          │             │
              ▼          ▼          ▼       ▼          ▼             ▼
        DISMISSING → CLOSED（reason = timeout / manual / superseded /
                                     action / host_closed / plugin_unloaded）
```

| 状态 | 含义 | 对外可见 |
| --- | --- | --- |
| `QUEUED` | 已受理，等待 GUI 线程渲染或同帧合并（≤100ms） | `handle.state` |
| `SHOWN` | 已渲染且计时中 | 是 |
| `UPDATING` | 正在变更内容/进度（瞬时态，不单独上报） | 否 |
| `DISMISSING` | 淡出动画中，不可再 update | 是 |
| `CLOSED` | 已销毁；`reason` 与 `on_dismiss` 已触发 | 是 |

约束：

- `update()` 在 `DISMISSING`/`CLOSED` 上调用 → 返回 `TOAST_UPDATING_CLOSED`，不复活。
- `dismiss()` 幂等；重复调用返回 `False`。
- 句柄持有弱引用语义：宿主销毁后句柄仍可查询 `state == CLOSED`，不会访问已删除的 Qt 对象。

### 4.4 持续时间 `ToastDuration`

```python
life: int | None = None   # None = 按级别默认；0 = 常驻；>0 = 显式毫秒
```

| 规则 | 值 |
| --- | --- |
| 基础时长 | `AppSettings.feedback.toast_life`（默认 3000），作为 success/info 的基准 |
| warn | `base × 2`（6000） |
| error | `base × 2.6`，上限 8000 |
| neutral | `base × 0.66`，下限 1500 |
| 非持久上限 | 15000（超出钳制 + `TOAST_LIFE_CLAMPED`） |
| 持久看门狗 | 120000：未收敛的 loading/progress 自动关闭（`reason=FAILED`，`code=TOAST_LEAK_AUTO_CLOSED`） |
| 悬停暂停 | 指针进入暂停计时，离开重新计满（现有 `CToast` 行为，保留） |
| 窗口最小化 | 计时继续；恢复后剩余时间 ≥1s，不足则立即关闭 |

时长是**建议值不是契约**：用户可在 `feedback` 设置段调整；插件不得依赖"一定停留 N 毫秒"做业务逻辑。

### 4.5 手动关闭与清理

| 能力 | 签名 | 说明 |
| --- | --- | --- |
| 单条关闭 | `handle.dismiss(reason=MANUAL, immediate=False)` | 幂等 |
| 按 id 关闭 | `ctx.toast.dismiss(toast_id, reason=MANUAL)` | 跨模块关闭（如"取消"按钮） |
| 通道清理 | `ctx.toast.clear(channel=None)` → 关闭条数 | `channel=None` 表示本插件全部通道 |
| 全局清理 | `ctx.toast.clear_all()` | 仅基座/测试使用；插件侧不暴露 |
| 关闭按钮 | `closable=True`（默认） | `closable=False` 仅用于 P2 的"强制阅读"错误，且必须有 action |
| 插件卸载 | 加载器调用 `router.clear_plugin(plugin_id)` | 全部以 `PLUGIN_UNLOADED` 收敛，避免悬空回调 |

**热重载铁律**：`on_unload` 之后任何 `handle.update()` 都必须安全失败（`TOAST_PLUGIN_UNLOADED`），
不得触发插件代码回调 —— 否则热重载后旧模块对象被新模块覆盖，闭包会访问已销毁控件。

### 4.6 去重

```python
dedupe_key: str = ""            # 空 = 自动按 f"{level}:{title}:{text}" 归一
dedupe: DedupePolicy = SUPPRESS
dedupe_window: int = 1200       # ms；<=0 表示不启用去重
```

| 策略 | 命中同键时 | 返回 | 典型场景 |
| --- | --- | --- | --- |
| `SUPPRESS` | 丢弃新请求，复用已有 toast | `ok=True, code=TOAST_DUPLICATE_SUPPRESSED, duplicate_of=<id>` | 连点"刷新"、快捷键连发 |
| `RESTART` | 复用已有 toast，重置计时，`repeat += 1` | 已有句柄 | 反复保存/切换，只保留最新一条 |
| `COUNT` | 复用并渲染计数（正文含 `{count}` 则插值，否则追加 `(×N)`） | 已有句柄 | 批量删除逐项确认、批处理逐条失败 |
| `REPLACE` | 关闭旧条（`REPLACED`），新建 | 新句柄 | 状态流滚动（播放提示、同步进度） |

隔离规则：

1. 去重键作用域 = `(scope, channel, dedupe_key)`；不同插件、不同通道互不影响。
2. `dedupe_window` 自**首次显示**起算，`RESTART`/`COUNT` 命中后顺延。
3. 自动键必须包含级别：`warn` 与 `error` 文案相同也不得互相吞掉。
4. 持久 toast（loading/progress）不参与时间窗去重，改用 `toast_id` 更新（见 §4.7）。

### 4.7 通道、队列与并发

```python
channel: str = ""                    # 空 = 本插件默认通道
mode: ToastMode = STACK              # stack | replace | coalesce
```

| 模式 | 通道容量 | 新条入栈行为 |
| --- | --- | --- |
| `STACK` | `feedback.toast_max`（默认 4，全局共享） | 新条置顶；满则按 §4.7.2 裁决 |
| `REPLACE` | 1 | 旧条 `REPLACED`，新条置顶（等价于固定 `dedupe_key` 的 `REPLACE`） |
| `COALESCE` | 1 | 同键合并：刷新文案、重置计时、`repeat += 1`；不同键按 `REPLACE` |

#### 4.7.1 队列模型

- **没有阻塞队列**。toast 是瞬时反馈，等待只会让信息过期；受理即渲染或立即裁决。
- `QUEUED` 只覆盖"跨线程投递"与"同一帧内多次 show"的合并窗口（≤100ms）。
- 全局栈按锚点窗口独立计数；主窗口与设置窗口互不挤占。

#### 4.7.2 溢出裁决（栈已满）

1. 先尝试挤掉**同通道最旧**的非 `error` 条（`SUPERSEDED`）。
2. 否则挤掉**级别最低**的非 `error` 条（neutral < info < success < warn）。
3. `error` 条与带 action 的条**永不被挤**；若全部为 `error`，丢弃新条并返回 `TOAST_STACK_FULL`（遥测告警，用户界面无变化）。
4. 被挤出的条必定触发 `on_dismiss(reason=SUPERSEDED)`，调用方可据此重排。

#### 4.7.3 并发与线程

| 规则 | 说明 |
| --- | --- |
| 任意线程可调 | 非 GUI 线程调用经 `QMetaObject.invokeMethod(..., QueuedConnection)` 投递，保持单线程顺序 |
| 去重/裁决在 GUI 线程 | 避免跨线程竞态；跨线程请求按到达顺序串行判定 |
| 进度合并 | 同一 `toast_id` 的 `update(progress=)` 100ms 内合并，只渲染最后一次 |
| 回调线程 | `on_dismiss` / `on_action` 一律在 GUI 线程执行，异常被隔离（记日志，不冒泡） |
| 限流 | 每插件 20 次 `show()` / 2s，超出丢弃并返回 `TOAST_RATE_LIMITED`；`update()` 不计入 |

> 限流存在的理由：文件监听、网络轮询类插件（如 py-listen 的目录自动同步）在异常情况下
> 会每几百毫秒弹一条；限流把"信息风暴"降级为"静默 + 一次遥测"。

### 4.8 回调与事件

```python
on_dismiss: Callable[[ToastDismiss], None] | None
on_action: Callable[[str], None] | None
```

`ToastDismiss` 载荷：

| 字段 | 说明 |
| --- | --- |
| `toast_id` | 稳定 id（`t-<scope>-<seq>`） |
| `reason` | `timeout` / `manual` / `replaced` / `cleared` / `superseded` / `action` / `host_closed` / `plugin_unloaded` / `failed` |
| `level` / `channel` | 冗余便于回调内分支 |
| `code` | 该条携带的业务/协议错误码（见 §4.9） |
| `repeat` | 去重合并次数 |
| `duration_ms` | 实际显示时长（自 SHOWN 起算） |
| `by_user` | 是否用户主动（点关闭 / 点 action） |

总线事件（经 `ctx.event` 上报，**不含正文**，避免隐私与日志膨胀）：

| 事件 | payload |
| --- | --- |
| `toast.shown` | `toast_id` `level` `channel` `code` `repeat` `persistent` `text_key` `length` |
| `toast.updated` | `toast_id` `level` `progress` |
| `toast.dismissed` | `toast_id` `reason` `duration_ms` `by_user` |
| `toast.action` | `toast_id` `action_id` |

订阅方式：

- **插件内逻辑**：用 `on_dismiss` / `on_action` 回调（不跨插件）。
- **测试/宿主观察**：`toast_bus().observe(callback)`，返回退订函数（供基座测试与诊断）。
- 不提供跨插件订阅：toast 是**私有反馈通道**，跨插件广播走 `ctx.events`。

### 4.9 结果与错误码

`show()` 永远返回句柄，`handle.result` 给出受理结果：

| 码 | ok | 含义 | 用户可见 |
| --- | --- | --- | --- |
| `TOAST_OK` | ✔ | 已显示 | 是 |
| `TOAST_DUPLICATE_SUPPRESSED` | ✔ | 命中去重，复用已有条 | 已有一条 |
| `TOAST_QUEUED` | ✔ | 已受理，等待渲染（跨线程） | 稍后 |
| `TOAST_TEXT_TRUNCATED` | ✔ | 正文超长已截断 | 是（截断后） |
| `TOAST_LIFE_CLAMPED` | ✔ | 时长被钳制到上限 | 是 |
| `TOAST_INVALID_LEVEL` | ✔ | 级别非法，回落 `info` | 是（info） |
| `TOAST_PROGRESS_INVALID` | ✔ | 进度越界，钳到 [0,1] | 是 |
| `TOAST_PAYLOAD_DROPPED` | ✔ | payload 不可序列化/超大，已丢弃 | 是 |
| `TOAST_ACTION_UNSUPPORTED` | ✔ | 渲染器不支持动作按钮，已降级为纯文本 | 是（无按钮） |
| `TOAST_STACK_FULL` | ✘ | 栈满且全部为 error/带 action，新条丢弃 | 否 |
| `TOAST_RATE_LIMITED` | ✘ | 触发限流 | 否 |
| `TOAST_EMPTY_TEXT` | ✘ | `text` 为空或全空白 | 否 |
| `TOAST_NO_ANCHOR_WINDOW` | ✘ | 无可用窗口（无显示环境/全部关闭） | 否 |
| `TOAST_HOST_UNAVAILABLE` | ✘ | 未绑定 host（CLI/测试/无 GUI 宿主） | 否 |
| `TOAST_NOOP` | ✘ | 上下文未提供 toast 能力（`NoopToast`） | 否 |
| `TOAST_UPDATING_CLOSED` | ✘ | 对已关闭句柄 `update` | 否 |
| `TOAST_PLUGIN_UNLOADED` | ✘ | 插件已卸载，调用被拒 | 否 |
| `TOAST_INVALID_CHANNEL` | ✔ | 通道名非法，回落默认通道 | 是（默认通道） |
| `TOAST_STRICT_VIOLATION` | ✘ | 严格模式下的开发者错误（仅测试环境） | 否 |

另有一个**只出现在 `ToastDismiss.code`** 中的码：

| 码 | 含义 |
| --- | --- |
| `TOAST_LEAK_AUTO_CLOSED` | 持久条超过看门狗时限，被基座强制关闭（同时上报 error 级遥测） |

**严格模式**：环境变量 `SLLKGUI_TOAST_STRICT=1` 时，`TOAST_EMPTY_TEXT` / `TOAST_INVALID_LEVEL`
改为抛 `ValueError`，用于测试与 lint；生产环境永不抛错。

**业务错误码**：插件通过 `code="PYLISTEN_WEBDAV_FAILED"` 透传，协议只负责
"随 toast 一起上报 + 在 `ToastDismiss` 中回传"，不解释语义。

**基座错误码目录**：基座自己的码（`PLUGIN_*` / `GIT_*` / `SOURCE_*` / `SURFACE_BUILD_FAILED` 等）
由 `ToastCatalog` 映射到语言键，插件无需关心：

```python
# 基座内部：code → (语言键, 默认文案, 建议级别, 是否附带"查看日志"动作)
"PLUGIN_LOAD_FAILED": ("language.Toast.PLUGIN_LOAD_FAILED", "插件加载失败，详情见日志", "error", True)
"GIT_TIMEOUT":        ("language.Toast.GIT_TIMEOUT", "拉取超时，请检查网络后重试", "warn", False)
```

---

## 5. 插件 API（`ctx.toast`）

### 5.1 全量签名

```python
class GalleryToast(ABC):
    protocol_version: int          # 1
    def capabilities(self) -> frozenset[str]: ...
    # {"stack","replace","coalesce","dedupe","channels","progress","actions","update"}

    def show(
        self,
        text: str,
        *,
        title: str = "",
        level: ToastLevel | str = ToastLevel.INFO,
        detail: str = "",
        text_key: str = "",
        life: int | None = None,
        closable: bool = True,
        channel: str = "",
        mode: ToastMode | str = ToastMode.STACK,
        dedupe_key: str = "",
        dedupe: DedupePolicy | str = DedupePolicy.SUPPRESS,
        dedupe_window: int = 1200,
        anchor: ToastAnchor | str = ToastAnchor.AUTO,
        progress: float | None = None,
        actions: Sequence[ToastAction] = (),
        payload: Mapping[str, Any] | None = None,
        code: str = "",
        on_dismiss: Callable[[ToastDismiss], None] | None = None,
        on_action: Callable[[str], None] | None = None,
    ) -> ToastHandle: ...

    def loading(self, text: str, **kw: Any) -> ToastHandle: ...          # level=loading, life=0
    def progress(self, text: str = "", value: float | None = None, **kw: Any) -> ToastHandle: ...
    def dismiss(self, toast_id: str, *, reason: ToastDismissReason | str = "manual",
                immediate: bool = False) -> bool: ...
    def clear(self, channel: str | None = None) -> int: ...
    def active(self, channel: str | None = None) -> tuple[ToastHandle, ...]: ...


class ToastHandle(ABC):
    toast_id: str
    state: ToastState
    result: ToastResult            # ok / code / duplicate_of

    def update(self, *, text: str | None = None, title: str | None = None,
               level: ToastLevel | str | None = None, progress: float | None = None,
               life: int | None = None, persist: bool | None = None,
               actions: Sequence[ToastAction] | None = None,
               payload: Mapping[str, Any] | None = None) -> ToastResult: ...
    def succeed(self, text: str | None = None, *, detail: str = "", life: int | None = None) -> ToastResult: ...
    def fail(self, text: str, *, code: str = "", detail: str = "",
             life: int | None = None, actions: Sequence[ToastAction] = ()) -> ToastResult: ...
    def advance(self, value: float, text: str | None = None) -> ToastResult: ...
    def dismiss(self, reason: ToastDismissReason | str = "manual", *, immediate: bool = False) -> bool: ...
    def on_dismiss(self, cb: Callable[[ToastDismiss], None]) -> Callable[[], None]: ...
    def on_action(self, cb: Callable[[str], None]) -> Callable[[], None]: ...
```

`ToastAction`：

```python
@dataclass(frozen=True)
class ToastAction:
    action_id: str        # 回调里回传
    text: str             # 按钮文案（已本地化）
    style: str = "secondary"   # secondary | primary | danger
    dismiss: bool = True       # 点击后是否关闭
```

### 5.2 六个标准用法

```python
# 1) 成功 / 失败
ctx.toast.show(ctx.text("save.done", "已保存"), level="success")
ctx.toast.show(ctx.text("save.failed", "保存失败，请重试"), level="error",
               detail=str(exc), code="NOTES_SAVE_FAILED")

# 2) 去重：连点刷新只留一条
ctx.toast.show(ctx.text("refresh.done", "已刷新"), level="success",
               dedupe_key="list.refresh", dedupe="restart")

# 3) 加载 → 异步结果（同一句柄收敛，不新增第二条）
handle = ctx.toast.loading(ctx.text("webdav.testing", "正在测试连接…"),
                           channel="webdav", code="PYLISTEN_WEBDAV_TEST")
try:
    client.ping()
except Exception as exc:
    handle.fail(ctx.text("webdav.failed", "连接失败"), detail=str(exc), code="PYLISTEN_WEBDAV_TEST_FAILED")
else:
    handle.succeed(ctx.text("webdav.ok", "连接成功"))

# 4) 进度（页内已有进度区时可不用 toast）
task = ctx.toast.progress(ctx.text("import.running", "正在导入"), channel="import")
task.advance(0.35, ctx.text("import.step", "正在转换皮肤…"))

# 5) 单通道状态流：播放提示只保留最新一条
ctx.toast.show(text, level="info", channel="player", mode="replace", life=1500)

# 6) 批量结果 + 动作
ctx.toast.show(
    ctx.text("import.summary", "导入完成：{ok} 成功 / {failed} 失败", ok=3, failed=1),
    level="warn",
    actions=(ToastAction("details", ctx.text("common.details", "查看详情")),),
    on_action=lambda action_id: self._open_import_report(),
)
```

### 5.3 与 `run_task` 的桥接（推荐写法）

```python
def done(result): handle.succeed(ctx.text("scan.done", "已扫描 {n} 首", n=len(result)))
def failed(msg):  handle.fail(ctx.text("scan.failed", "扫描失败"), detail=msg, code="PYLISTEN_SCAN_FAILED")
run_task(self, worker, name="pylisten.scan", on_done=done, on_error=failed)
```

`run_task` 的回调已经在 GUI 线程，且 `on_error` 只给字符串 —— 与 `fail(text, detail=...)` 正好对齐。

---

## 6. 场景覆盖矩阵

> 口径：**"瞬时、非阻塞、无需用户输入"** 这一类反馈共 18 个场景类，协议 18/18 有定义。
> 其中 14 类由协议原生表达，4 类（确认/字段校验/常驻横幅/系统通知）由协议**显式指派**到既有组件。
> 因此不存在"协议没规定、插件只好自己画"的中间地带 —— 这是"≥99%"的实质含义。

| # | 场景 | 协议表达 | 覆盖 |
| --- | --- | --- | --- |
| 1 | 操作成功 | `level=success` | ✅ |
| 2 | 操作失败 | `level=error` + `detail` + `code` | ✅ |
| 3 | 部分成功/降级 | `level=warn` + 汇总文案 | ✅ |
| 4 | 中性信息 | `level=info` | ✅ |
| 5 | 极轻量确认（复制/刷新） | `level=neutral` + 短时长 | ✅ |
| 6 | 加载中（不确定） | `level=loading`（常驻）+ 句柄收敛 | ✅ |
| 7 | 确定进度 | `level=progress` + `advance()` | ✅ |
| 8 | 异步结果回执 | `loading → succeed/fail` 同句柄 | ✅ |
| 9 | 批量结果摘要 | 单条汇总 + `actions`（查看详情） | ✅ |
| 10 | 可撤销/可重试 | `error` / `warn` + `ToastAction(undo/retry)` | ✅ |
| 11 | 高频同义提示 | `dedupe=suppress/restart/count` | ✅ |
| 12 | 状态流滚动（播放提示） | `mode=replace` 通道 | ✅ |
| 13 | 连点/风暴保护 | 限流 + `TOAST_RATE_LIMITED` | ✅ |
| 14 | 跨窗口结果（设置页动作） | `anchor=auto`（活动模态优先） | ✅ |
| 15 | 破坏性确认 | **指派** `CConfirmDialog` | ◐ |
| 16 | 字段级校验 | **指派** `CMessage(simple=True)` | ◐ |
| 17 | 常驻状态（离线/只读） | **指派** 内联 `CMessage` / 状态标签 | ◐ |
| 18 | 窗口不在前台的系统提醒 | **指派** `ctx.tray.show_message` | ◐ |

补充规则（场景 15–18 的判定）：

```text
需要用户选择/输入？ ── 是 ──► CDialog / CConfirmDialog
        │ 否
需要定位到具体字段？ ── 是 ──► CMessage(simple=True)
        │ 否
会持续存在直到状态改变？ ── 是 ──► 内联 CMessage / 状态标签 / CChip
        │ 否
窗口当前可见？ ── 否 ──► ctx.tray.show_message（需权限）
        │ 是
        └────────────► ctx.toast
```

---

## 7. 注册规范（强制）

### 7.1 接入声明

- **不需要清单权限**：toast 是本进程 UI，不涉及外部副作用（与 `notifications` 区分）。
- **不新增清单字段**：能力通过 `ctx.toast` 是否存在 + `capabilities()` 探测。
- **首次调用即注册**：`ctx.toast.show()` 自动把 `plugin_id` 注册为去重/限流作用域。
- **推荐集中声明**：插件内建 `toasts.py` 作为"toast 注册表"，把通道、去重键、文案键收敛到一处，
  业务代码只调语义函数（便于静态检查与文案审计）。

```python
# toasts.py —— 插件内的 toast 注册表（推荐结构）
from enum import StrEnum

class Channel(StrEnum):
    PLAYER = "player"
    WEBDAV = "webdav"
    LIBRARY = "library"
    DOWNLOAD = "download"

class Key(StrEnum):
    PLAYER_NOTICE = "player.notice"
    WEBDAV_TEST = "webdav.test"
    LIBRARY_SCAN = "library.scan"

def notify_saved(ctx, name: str) -> None:
    ctx.toast.show(ctx.text("status.saved", "已保存「{name}」", name=name),
                   level="success", channel=Channel.LIBRARY,
                   dedupe_key="library.save", dedupe="restart")

def notify_failed(ctx, message: str, *, code: str, detail: str = "") -> None:
    ctx.toast.show(ctx.text("status.failed", "操作未能完成，请重试"), level="error",
                   channel=Channel.LIBRARY, code=code, detail=detail)
```

### 7.2 通道命名

| 规则 | 示例 |
| --- | --- |
| 基座原生页用 `base.<area>` | `base.plugin_store`、`base.settings` |
| 插件用 `<area>`（作用域已带 `plugin_id`，不重复拼） | `player`、`webdav`、`import` |
| 正则 `^[a-z0-9][a-z0-9._-]{0,47}$` | 超长/非法 → `TOAST_INVALID_CHANNEL`，回落默认通道 |
| 一个语义流一个通道 | 播放提示 `player`；下载 `download`；设置动作 `webdav` |

### 7.3 去重键命名

- 形式 `<资源>.<动作>`，小写点分：`library.scan`、`webdav.test`、`download.add`。
- 必须是**稳定字面量**，不得拼接用户输入或时间戳（否则去重永不命中）。
- 同一 key 的级别必须稳定：不要在 `success` 与 `error` 间复用同一个 key。

### 7.4 级别选择决策树

```text
操作完成了？ ── 是 ──► 用户需要知道结果吗？ ── 否 ──► 不弹（日志/遥测）
      │ 是                        │ 是
      │                          └──► success（有变更）/ info（无变更）/ neutral（极轻量）
      └ 否 ──► 还能继续用吗？ ── 是 ──► warn（说明代价 + 补救）
                        │ 否
                        └──► error（说明原因 + 下一步；带 detail 与 code）
进行中且结果未知 ──► loading（常驻，必须收敛）
可量化 ──► progress（常驻，advance）
```

### 7.5 文案规范

1. 一句话说清**发生了什么 + 下一步**："连接失败，请检查地址与密码"，而不是 "Error 401"。
2. 不出现内部标识：错误码、异常类名、文件绝对路径 → 放 `detail`。
3. 不使用感叹号堆叠、不使用"操作成功"这类空话（成功文案应包含对象：`已启用「时钟」`）。
4. 正文不带标题时也能独立读懂；带 `title` 时标题是类别，正文是细节。
5. 语言键必须进 `resource/lang/*.yml`，禁止硬编码中文（lint 已有语言检查，可扩展 key 前缀校验）。

### 7.6 时长与常驻

| 允许覆盖 `life` 的情形 | 说明 |
| --- | --- |
| 需要阅读的长错误 | `life=8000~12000` |
| 极轻量确认 | `life=1500` |
| `loading`/`progress` | 必须 `life=0` + 句柄收敛 |
| 其它 | 不要覆盖，交给级别默认值 |

### 7.7 配对规则（防泄漏）

- 每个 `loading` / `progress` 必须在**同一函数/同一回调对**里收敛为 `succeed` / `fail` / `dismiss`。
- 允许的唯一例外：句柄交给后续回调持有（此时必须注册 `on_dismiss` 清理本地引用）。
- 禁止"只发 loading 不管结果"；看门狗会在 120s 后兜底关闭并上报 `TOAST_LEAK_AUTO_CLOSED`。
- 插件 `on_unload` 不需要手动清 toast —— 加载器统一 `clear_plugin`。

### 7.8 音量控制

| 规则 | 说明 |
| --- | --- |
| 一次用户动作 ≤1 条 toast | 不要"逐项成功"刷屏，用汇总 + 计数 |
| 同一通道同一时刻 ≤1 条（状态流） | 用 `mode=replace` |
| 循环/轮询类事件 → 不弹 toast | 目录监听、网络心跳改为内联状态 |
| 批量失败 → 1 条 warn/error + `details` 动作 | 明细放对话框 |

### 7.9 禁止清单

| 禁止 | 替代 |
| --- | --- |
| `QMessageBox` | `CConfirmDialog` / `CDialog` / `ctx.toast` |
| 自绘顶层浮层、`QSystemTrayIcon.showMessage` 直调 | `ctx.toast` / `ctx.tray.show_message` |
| 插件内直接 `CToast.show_message(...)`（4.2 起 lint 提示） | `ctx.toast` |
| 用 `statusBar` / 临时 `QLabel` 承载一次性结果 | `ctx.toast`（常驻状态才用标签） |
| 在 worker 线程直接操作 Qt 控件 | `ctx.toast` 可跨线程，其它控件不行 |

### 7.10 测试钩子

```python
# 插件测试：用记录型宿主，不启动真实窗口
from sllkgui.gallery.toast import ToastRouter, RecordingHost
router = ToastRouter(host=RecordingHost())
plugin_ctx = FakeContext(toast=router.handle("com.example.notes"))
plugin_ctx.toast.show("已保存", level="success")
assert router.host.records[-1].level == "success"
```

- 协议层单测不需要 Qt：`ToastRouter` 可注入 `RecordingHost`。
- UI 层交互测试用 `pytest-qt` + `qtbot.waitSignal`，断言 `closed` 与 `ToastDismiss.reason`。
- 严格模式 `SLLKGUI_TOAST_STRICT=1` 让开发者错误在 CI 直接失败。

---

## 8. 实现落点（文件级）

### 8.1 阶段 P1（协议可用，外观不变）

| # | 文件 | 变更 |
| --- | --- | --- |
| 1 | `gallery/api.py` | 新增 `ToastLevel` `ToastMode` `DedupePolicy` `ToastState` `ToastDismissReason` `ToastAnchor` `ToastAction` `ToastDismiss` `ToastResult` `ToastHandle` `GalleryToast`；`GalleryContext` 增加**非抽象**属性 `toast`（返回 `NOOP_TOAST`）。`NoopToast` 定义在本文件内，避免与 `toast.py` 循环导入 |
| 2 | `gallery/toast.py`（新） | `ToastRouter`（作用域/限流/遥测/卸载清理）、`PluginToast`（`GalleryToast` 实现）、`NoopToast`、`RecordingHost` |
| 3 | `gallery/context.py` | 构造参数新增可选 `toast: ToastRouter`；`toast` 属性返回 `PluginToast` 或 `NOOP_TOAST` |
| 4 | `gallery/loader.py` | `load_plugin(..., toast=...)` 透传；卸载分支调用 `router.clear_plugin(plugin_id)` |
| 5 | `gallery/runtime.py` | `self.toast = ToastRouter()`；`attach_window()` 时绑定 host；`shutdown()` 清空 |
| 6 | `gallery/window.py` | 新增 `_toast_host(request)`：解析锚点（§3.2）、计算标题栏偏移、调用 `toast_bus().show(...)`；`closeEvent` 触发 `HOST_CLOSED` |
| 7 | `plugin.py` | 导出 `GalleryToast` `ToastLevel` `ToastAction` `ToastDismiss` `ToastResult` `ToastHandle` |
| 8 | `guicore/feedback/toast_bus.py`（新） | `ToastBus`：通道表、去重、溢出裁决、状态机、线程投递、`observe()`、`reset_toast_bus()` |
| 9 | `guicore/custom_ui/feedback/toast.py` | 新增 `set_content(text, title, level)`、`set_persistent(bool)`、`set_severity()`、`dismiss_reason` 属性；内部暴露 `_finish(reason)`；`show_message` 保持签名不变（内部改走同一路径） |
| 10 | `guis/pages/plugin_store/page.py` | `set_status()` 改调 `toast_bus()`（`channel="base.plugin_store"`, `mode="replace"`）；`_fail()` 用 `ToastCatalog` 由 `error_code` 生成文案 + `detail` |
| 11 | `guis/pages/plugin_store/theme.py` | 删除 `_toast_offset()`（偏移由 host 统一计算） |
| 12 | `guis/windows/main_window/registry.py` | 失败分支返回 `(ok, code)` 或直接发一条基座 toast（消除 6 个静默 return） |
| 13 | `guicore/window/settings_window/window.py` | 草稿失效改走 `toast_bus()`（`base.settings`） |
| 14 | `docs/TOAST.md`（本文） + `docs/README.md` 索引 | 文档 |

### 8.2 阶段 P2（渲染器增强）

| # | 变更 | 目的 |
| --- | --- | --- |
| 1 | `CToast` 增加加载指示（`loading` 级用旋转图标） | 场景 6 |
| 2 | 增加进度条（`progress` 级渲染 `0..1`） | 场景 7 |
| 3 | 增加动作按钮区（≤2 个） | 场景 9/10 |
| 4 | 增加计数徽标 `(×N)` | 去重 `COUNT` |
| 5 | `detail` 的 tooltip / "查看日志" 动作 | 错误可定位 |
| 6 | 文本超过 3 行折叠 + 展开 | 长错误 |

> P2 缺失时协议**不阻塞**：`actions` 降级为纯文本（返回 `TOAST_ACTION_UNSUPPORTED`），
> `progress` 降级为文案内百分比，`loading` 降级为 `info` + 常驻。

### 8.3 关键实现约束

1. `gallery/toast.py` **不得 import PySide6**（`gallery.api` 的现有约定），Qt 只能经 host 回调进入。
2. `guis` 仍不 import `gallery`：原生页用 `toast_bus()`，不碰 `ctx.toast`。
3. `gallery → guis` 的新增 import 只允许出现在 `gallery/window.py`（`EDGE_ALLOWLIST`）。
4. `CToast.show_message(...)` 的既有行为（会话数、`closed` 信号、`clear`）必须保持，
   `tests/test_feedback_components.py` / `tests/test_toast_interaction.py` 不得回归。
5. 渲染器只做"画"，不做"裁决"：去重、限流、溢出全部在 `ToastBus`，便于无 Qt 单测。

---

## 9. 兼容性与迁移

### 9.1 版本策略

| 版本 | 变更 |
| --- | --- |
| 4.1 | 协议 v1 落地；`ctx.toast` 以**非抽象属性**加入（`NoopToast` 兜底）；`CToast` 直调保留；文档 + 严格模式 |
| 4.2 | 基座原生页全部切到 `toast_bus()`；插件 `CToast` 直调在 lint 中降为警告（`plugin-lint` 新增规则 `toast-direct-use`） |
| 5.0 / API 3 | `ctx.toast` 转为必需能力；插件侧 `CToast` 不再保证签名稳定；`severity` 旧枚举仅保留别名 |

**为什么 API 2 不升版**：新增属性不是破坏性变更（`Plugin` / `GalleryContext` 的实现由基座提供，
插件只消费）；把"可选能力"强行升版会让现有 py-rm / py-listen 无法在新基座上运行。

### 9.2 兼容矩阵

| 组合 | 行为 |
| --- | --- |
| 新基座 + 旧插件（直调 `CToast`） | 正常工作；无去重/无遥测/无卸载清理（现状） |
| 新基座 + 新插件（`ctx.toast`） | 全能力 |
| 旧基座（4.0.x）+ 新插件（用 `ctx.toast`） | `AttributeError`；插件须 `getattr(ctx, "toast", None)` 探测并回落 |
| 无 GUI 宿主 / CLI | `NoopToast` → `TOAST_NOOP`；业务不中断 |
| 测试替身 `GalleryContext` 子类 | 未覆写 `toast` 时继承 `NoopToast`，不破坏既有测试 |

插件侧兼容写法（建议写入 PLUGIN.md 迁移段）：

```python
toast = getattr(ctx, "toast", None)
if toast is None:
    ctx.log(message, "info")     # 旧基座：降级为日志
else:
    toast.show(message, level="success")
```

### 9.3 从现有封装迁移（三步）

1. **建注册表**：新增 `toasts.py`，把现有 `_toast` / `_set_status` 的文案键与通道集中声明。
2. **替换调用**：`_set_status(txt, "danger")` → `ctx.toast.show(txt, level="error", channel=..., code=...)`；
   单条替换语义 → `mode="replace"`；`_toast(..., "warning")` → `level="warn"`。
3. **删除私有壳**：移除 `_toast_offset()` / `_TOAST_OFFSET` / `_forget_toast()` 等偏移与句柄簿记代码。

### 9.4 兼容性风险

| 风险 | 缓解 |
| --- | --- |
| 插件把 `severity="danger"` 传给新 API | 别名表接受（§4.1） |
| 插件依赖"每次 show 都新建一条" | `STACK` 是默认模式，只有显式 `dedupe`/`mode` 才合并 |
| 插件在 `on_unload` 之后仍回调 | `PLUGIN_UNLOADED` 安全失败 + 加载器统一清理 |
| 长驻 toast 引用已销毁页面 | 句柄弱引用 + 锚点窗口化 |
| 现有视觉回归 | P1 不改外观；仅 P2 增加加载/进度/按钮 |

---

## 10. 验收与测试关注点

### 10.1 验收标准（P1 完成时）

| # | 验收项 | 判定 |
| --- | --- | --- |
| 1 | 协议层无 Qt | `python -c "import sllkgui.gallery.toast"` 不拉 PySide6 |
| 2 | 三项目接入 | py-rm / py-listen 再无 `CToast` 直调；插件管理页无 `_toast_offset` |
| 3 | 去重 | 同键连发 10 次 → 1 条 + `repeat=10`（`restart` 策略） |
| 4 | 溢出 | 5 条 info + 1 条 error → error 必在，被挤者收到 `SUPERSEDED` |
| 5 | 跨线程 | worker 线程 `show()` 不崩，顺序与调用一致 |
| 6 | 热重载 | 卸载后 1s 内 `update()` 返回 `TOAST_PLUGIN_UNLOADED`，无异常日志 |
| 7 | 跨窗口 | 设置页动作的 toast 出现在设置窗口（非主窗口） |
| 8 | 无宿主 | CLI 路径返回 `TOAST_NOOP`，日志有记录，退出码为 0 |

### 10.2 测试关注点（按层）

| 层 | 用例 | 方法 |
| --- | --- | --- |
| 协议（无 Qt） | 级别归一、别名、错误码、去重四策略、溢出裁决、限流、`code` 透传 | `ToastRouter` + `RecordingHost`，纯 pytest |
| UI 总线 | 通道容量、`replace`/`coalesce`、状态机、看门狗、线程投递 | `qtbot` + 假渲染器（注入 `renderer_factory`） |
| 渲染器 | `set_content` 更新、`persistent` 不自动关、悬停暂停、`closed` 信号 | 现有 `tests/test_toast_interaction.py` 扩展 |
| 跨层 | `ctx.toast` → 基座 toast 出现；卸载清理；语言切换后新文案生效 | `tests/test_gallery_toast_bridge.py`（新） |
| 回归 | `CToast.show_message` 旧签名/堆叠/clear；`test_feedback_components.py` 全绿 | 现有用例不改 |
| 插件侧 | py-rm 单条状态替换、py-listen 设置动作 loading→结果、播放提示不堆叠 | 插件仓库内用记录型宿主 |

### 10.3 易错点（写测试时优先覆盖）

1. **锚点为页面**：切页后 toast 立刻消失 —— 断言切页后仍可见。
2. **未知级别**：`level="critical"` 必须回落 `info`，不能抛 `ValueError`。
3. **持久泄漏**：`loading` 不收敛 → 看门狗 120s 关闭（测试注入短超时）。
4. **去重误吞**：`warn` 与 `error` 同文案不得互相抑制。
5. **卸载竞态**：`on_dismiss` 在卸载后触发会访问已销毁控件 —— 必须被拦截。
6. **空文本**：`text=""` 直接丢弃（`TOAST_EMPTY_TEXT`），不得渲染空气泡。
7. **超长文本**：500 字符截断，不得把 340px 宽的卡片撑成整屏。
8. **限流误伤**：`update(progress=)` 不计入限流，否则进度条会中途消失。

---

## 附录 A：错误码速查

| 分组 | 码 |
| --- | --- |
| 受理成功 | `TOAST_OK` `TOAST_QUEUED` `TOAST_DUPLICATE_SUPPRESSED` |
| 降级但可见 | `TOAST_TEXT_TRUNCATED` `TOAST_LIFE_CLAMPED` `TOAST_INVALID_LEVEL` `TOAST_PROGRESS_INVALID` `TOAST_PAYLOAD_DROPPED` `TOAST_ACTION_UNSUPPORTED` |
| 静默丢弃 | `TOAST_STACK_FULL` `TOAST_RATE_LIMITED` `TOAST_EMPTY_TEXT` `TOAST_NO_ANCHOR_WINDOW` `TOAST_HOST_UNAVAILABLE` `TOAST_NOOP` `TOAST_UPDATING_CLOSED` `TOAST_PLUGIN_UNLOADED` `TOAST_STRICT_VIOLATION` |
| 降级但可见（续） | `TOAST_INVALID_CHANNEL` |
| 仅 dismiss 载荷 | `TOAST_LEAK_AUTO_CLOSED` |

## 附录 B：`CToast` / `Severity` 映射

| 旧调用 | 新协议 |
| --- | --- |
| `CToast.show_message(p, text, title, "info")` | `show(text, title=title, level="info")` |
| `... severity="success"` | `level="success"` |
| `... severity="danger"` | `level="error"` |
| `... severity="warning"` | `level="warn"` |
| `... life=0` | `life=0`（持久，须收敛） |
| `... life=6000` | `life=6000` |
| `... offset_top=56` | 删除；由 host 统一计算 |
| `CToast.clear(p)` | `ctx.toast.clear()` / `toast_bus().clear(anchor)` |
| 页面级单条替换（`dismiss` 上一条） | `mode="replace"` + `channel` |

## 附录 C：变更记录

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-11-22 | v1 设计稿 | 首次定义：7 级类型、句柄模型、去重/通道/溢出/限流、19 个协议码、注册规范、场景矩阵、实现落点 |
