# Toast 统一接入审计与改造清单

> 审计对象：`D:/ReworkPRG/SllkGuiPRG` 工作区快照
> 基座 `SllkGui` 4.0.2（插件协议 API 2）、`py-rm` 3.2.0、`py-listen` 1.12.3
> 审计日期：2026-11-22 · 方法：全量读码 + AST 统计调用点 + `grep` 交叉核对
> 协议依据：[docs/TOAST.md](../TOAST.md)（v1 设计稿）
>
> **行号基于本次快照，重构后可能漂移；表格以「文件 + 函数名」为主键，行号仅作定位参考。**
> 统计口径：AST 计 `Call` 节点，不含函数定义本身。
>
> 本轮审计与改造**同批完成**：§0 是实施结果，§2–§5 保留改造前的现状快照（用于回溯
> 「为什么这么改」），当前代码已不含其中多数私有封装。

---

## 0. 实施结果（同批完成）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| 协议骨架（模型 / 总线 / 路由 / 门面） | ✅ | `appcore/feedback.py`、`guicore/feedback/toast_bus.py`、`gallery/toast.py`、`guicore/feedback` 包；`import` 不拉 Qt（子进程断言） |
| 渲染器增强（更新/进度/动作/计数/折叠） | ✅ | `custom_ui/feedback/toast.py`；`CToast.show_message` 旧契约保留 |
| 基座原生页接入 | ✅ | 插件管理页 `set_status`/`_fail`（含「复制错误信息」动作与码表）、设置窗口草稿提示、`gallery/window._notify_failure`、`registry.ensure_registered_page` 的 6 个失败分支 |
| py-rm 接入 | ✅ | `_set_status` 单通道替换；补齐置顶/桌面层对称回执；旧基座降级为日志 |
| py-listen 接入 | ✅ | `_toast` 适配、播放提示 `replace` 通道、WebDAV 三条 loading 收敛、页脚重复提示去除、下载完成/失败与队列清空回执；`ui/notify.py` 统一旧基座降级 |
| 测试 | ✅ | 新增 `test_toast_protocol.py`（15）、`test_toast_bus.py`（17）、`test_toast_bridge.py`（5）、`test_notify.py`（4）；基座 842 / py-rm 259 / py-listen 77 全绿 |
| R-15 大备份阻塞 | ⚠ 未改 | `import_backup` 复用主线程 sqlite 连接（连接有线程亲和性），需先重构 DB 连接模型；已在代码注释与协议审计标注 |

> 结论：89 条改造中，除 R-15 需要独立的 DB 线程模型改造外，其余全部落地。
> 「保留」项（确认对话框、字段校验、对话框内联页脚、托盘通知）按协议边界保持原样。

## 1. 结论摘要

| 项 | 数值 | 说明 |
| --- | --- | --- |
| 现有 toast 调用点 | **55** | 基座 12 + py-rm 22 + py-listen 21（15 `_toast` + 2 `_show_toast` + 4 `online._toast`） |
| 私有封装层 | **4 套** | `plugin_store.set_status`、py-rm `_set_status`、py-listen `_toast`、`_show_toast` |
| 硬编码顶部偏移 | **3 处** | `_toast_offset()`×2、`_TOAST_OFFSET = 58` |
| 锚点绑页面（切页即消失） | **1 处** | py-rm 以 `self`（页面）为 parent |
| 需改造条目 | **89** | 转换现有调用点 + 内联状态升级 + 静默补齐；分级见 §6 |
| 明确保留（非 toast 场景） | **16 组** | 确认对话框、字段校验、对话框内联页脚、托盘通知 |
| 渲染器增强项 | **7** | 更新内容、进度、动作按钮、计数、加载指示等（§3.3 末表） |
| 新增分层守卫 | **1** | `gallery/toast.py` 不得 import PySide6 |

**分级口径**（贯穿全文）：

| 级别 | 含义 | 典型 |
| --- | --- | --- |
| **P0** | 正确性：错误路径、静默失败、锚点/偏移错位、崩溃或泄漏 | 页面构建失败无提示、错误码丢失、toast 随页面消失 |
| **P1** | 一致性：时长、去重、重复提示、级别、文案口径 | 同文案同时进页脚与 toast、`danger`/`warning` 混用 |
| **P2** | 体验细节与增强 | 队列清空无回执、启动期降级聚合 |

> 89 条不等于 89 次改动：多数条目由**替换同一个封装**一次性覆盖
> （例如删掉 `tools_dialogs._toast` 一次修好 15 条）。实际改造单位约 6 个封装 + 12 个静默入口。


**核心问题不是"没有 toast"，而是每个项目自己实现了一套策略**：时长、去重、替换语义、
避让偏移、锚点各写一遍，且互相不知道对方存在。结果同一屏可能同时出现 py-listen 的
"正在缓冲"与 py-rm 的"已启用「时钟」"，各自计时、各自偏移、各自消失。

---

## 2. 现状对照

### 2.1 四套封装的语义差异

| 维度 | 基座 `set_status` | py-rm `_set_status` | py-listen `_toast` | py-listen `_show_toast` |
| --- | --- | --- | --- | --- |
| 位置 | `plugin_store/page.py:1146` | `control/page.py:1563` | `tools_dialogs.py:67` | `player_bar.py:246` |
| 锚点 | `ctx.parent_window()` | `self`（页面控件） | `QApplication.activeWindow()` → `ctx.parent_window()` | `self.window()` |
| 去重/替换 | 无（堆叠） | **单条替换**（先 `dismiss(immediate)` 上一条） | 无（堆叠） | **单条替换** |
| 时长 | error/warning 6000，其余 3000 | 全部默认 3000 | 全部默认 3000 | 全部默认 3000 |
| 顶部偏移 | `_toast_offset(window)` = 标题栏+8 | `_toast_offset()` = 页边距+页头+间距 | 设置窗口固定 58，其余 0 | 0 |
| 标题 | 固定"插件管理" | 固定"桌面小部件" | 可选，多数为空 | 无 |
| 级别别名 | 自己映射 `warning→warn` | 直接透传（"warning"/"danger"混用） | 透传 "danger" | 透传 "danger" |
| 失败可观测 | `report_error` + 通用文案 | `_log` + 通用文案 | 无（异常串直接进文案） | 无 |

### 2.2 直接使用 `CToast` 的位置

| 位置 | 用途 | 说明 |
| --- | --- | --- |
| `SllkGui/src/sllkgui/gallery/window.py:143` | 页面/路由加载失败 | 已是最接近协议的一处，但绕过统一入口 |
| `SllkGui/src/sllkgui/guicore/window/settings_window/window.py:574` | 设置草稿失效 | 走 `CToast` 直调 |
| `SllkGui/src/sllkgui/guis/pages/plugin_store/page.py:1154` | 插件管理全部状态 | 封装在 `set_status` |
| `py-rm/surfaces/control/page.py:1573` | 小部件全部状态 | 封装在 `_set_status` |
| `py-listen/ui/tools_dialogs.py:72` | 设置动作全部结果 | 封装在 `_toast` |
| `py-listen/ui/player_bar.py:254` | 播放提示/错误 | 封装在 `_show_toast` |
| `py-listen/ui/online_page.py:1607` | 下载入队结果 | 封装在 `_toast` |

---

## 3. 基座（SllkGui）

### 3.1 插件管理页 · `guis/pages/plugin_store/page.py`

| # | 行 | 函数 | 文案键 / 内容 | 场景 | 目标调用 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1165 | `_fail` | `status.failed`（通用） | error | `toast.show(text, level="error", code=error_code, detail=str(exc), actions=(ToastAction("log", "查看日志"),))` | **P0** |
| 2 | 1191 | `_run_async.done` | `success_message(result)` | success | `show(..., channel="base.plugin_store", mode="replace", dedupe="restart")` | P1 |
| 3 | 1240 | `_set_plugin_enabled` | `status.enabled_done` / `disabled_done` / `dependents_disabled` | success | 同上；`dependents>0` 时升 `warn` | P1 |
| 4 | 1257 | `_update_plugin` | `status.update_done` / `up_to_date` | success / info | `up_to_date` 用 `neutral` | P1 |
| 5 | 1276 | `_rollback_plugin` | `status.rollback_done` | success | 同 #2 | P1 |
| 6 | 1314 | `_remove_plugin` | `status.remove_done` | success | 同 #2 | P1 |
| 7 | 1335 | `_install_plugin` | `status.install_done` | success | 同 #2 | P1 |
| 8 | 1376 | `_submit_source` | `sources.url_required` | warn（校验） | `level="warn"`；输入框旁补内联错误 | P1 |
| 9 | 1388 | `_add_source.done` | `sources.added` | success | 同 #2 | P1 |
| 10 | 1427 | `_refresh_list` | `status.list_refreshed` | success | 同 #2 | P1 |
| 11 | 1449 | `_remove_source.done` | `status.action_done` | success | 同 #2 | P1 |
| 12 | 1474 | `_refresh_source.done` | `status.action_done` | success | 同 #2 | P1 |

同文件内**保留**（符合协议边界）：

| 行 | 内容 | 理由 |
| --- | --- | --- |
| 1299 / 1434 | `CConfirmDialog.ask`（卸载插件 / 移除来源） | 破坏性确认，需要阻断与焦点 |
| 1179 / 1210 / 1360 / 1424 / 1461 | `_busy` 早退（另有 1382 / 1431 的 `sources is None or _busy`） | 按钮已禁用；补提示反而制造噪音（见 §7 R-07） |

### 3.2 插件管理页 · 其它文件

| 文件 | 行 | 现状 | 建议 | 优先级 |
| --- | --- | --- | --- | --- |
| `plugin_store/theme.py` | 122 | `_toast_offset(window)` 读 `window.ui.title_bar.height()+8` | 删除；偏移由 toast host 统一计算 | P1 |
| `plugin_store/panels.py` | 66–80 | `BusyStrip`（页内活动条） | 保留（场景 17）；长任务离开页面后再用 `loading` toast | — |

### 3.3 基座其它位置

| # | 文件:行 | 函数 | 现状 | 场景 | 建议 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| 13 | `gallery/window.py:143` | `_notify_failure` | 直调 `CToast`，含目标 + 错误码 + "详情见日志" | error | 改走 `runtime.toast`：`code=` 透传、文案由 `ToastCatalog` 生成、附"查看日志"动作 | P1 |
| 14 | `guicore/window/settings_window/window.py:574` | `_rebuild_page` | 草稿失效 warn，`life=5000` | warn | `toast_bus().show(..., channel="base.settings")` | P1 |
| 15 | `guis/windows/main_window/registry.py:67–95` | `ensure_registered_page` | **6 个失败分支只写日志**：原生页工厂抛错 / 返回非 QWidget / 路由缺失 / 上下文缺失 / Surface 工厂抛错 / 返回非 QWidget | 静默 | 统一返回 `(False, code)`，由调用方发一条 error toast（对齐 RV-09） | **P0** |
| 16 | `guis/windows/main_window/controller.py:96` | `switch_page` | 忽略 `ensure_registered_page` 返回值 | 静默 | 拿到失败码后提示 | **P0** |
| 17 | `guis/windows/main_window/setup_main_window.py:85` | 默认页构建 | 同上 | 静默 | 同上（首屏失败尤其致命） | **P0** |
| 18 | `guis/language_service.py:311` | 语言切换后重建页 | 忽略返回值 | 静默 | 失败时 warn（"部分页面需重启"） | P2 |
| 19 | `showcase/core_preview/surfaces/feedback/page.py:92,99` | 组件预览 | 直接演示 `CToast.show_message` / `clear` | 演示 | 改为演示协议（去重、loading、进度、动作） | P1 |
| 20 | `showcase/core_preview/surfaces/overlays/page.py:35` | 浮层预览 | 自算 `offset_top` | 演示 | 删除偏移计算 | P2 |

**渲染器缺口**（`guicore/custom_ui/feedback/toast.py`）：

| # | 现状 | 影响 | 建议 |
| --- | --- | --- | --- |
| R1 | 只有 `show_message(...)` 一次性渲染，无 `set_content()` | 无法做 `loading → 结果` 同条收敛 | 增加 `set_content(text, title, level)` |
| R2 | 无进度渲染 | `progress` 级无法表达 | P2 增加进度条/环形 |
| R3 | 无动作按钮 | 错误无法给"重试/查看日志" | P2 增加 action 区 |
| R4 | `normalize_severity()` 对未知值抛 `ValueError` | 插件传 `critical` 直接打断业务 | 协议层先归一 + 兜底 `info` |
| R5 | `_stacks` 以 `id(parent)` 分组，页面销毁即丢失 | 切页后提示消失 | 锚点改为顶层窗口 |
| R6 | `life=0` 无兜底 | 忘记关闭的 loading 永久停留 | 120s 看门狗 |
| R7 | 无关闭原因 | 无法区分超时/手动/被挤出 | `_finish(reason)` + `closed` 带原因 |

---

## 4. py-rm

### 4.1 `surfaces/control/page.py` — 22 个 `_set_status` 调用点

| # | 行 | 函数 | 文案键 | 场景 | 目标级别 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1287 | `_on_widget_toggled` | `status.toggled_on/off` | success | success | P0 |
| 2 | 1298 | `_toggle_selected` | `status.toggled` | success | success | P0 |
| 3 | 1305 | `_refresh_selected` | `status.refreshed` | success | success（`neutral`，无变更） | P1 |
| 4 | 1311 | `_clear_through` | `status.clear_through` | success | success | P1 |
| 5 | 1319 | `_on_lock_toggled` | `status.locked/unlocked` | success | success | P1 |
| 6 | 1343 | `_on_desktop_toggled` | `status.desktop_on`（仅开启时） | success | success（**关闭时也补**） | P1 |
| 7 | 1383 | `_save_skin_options` | `status.saved` / `msg_skin_option_invalid` | success / error | 按 `failure` 分支 | P0 |
| 8 | 1395 | `_reset_skin_options` | `_human_error(exc.info)` | error | error + `code=exc.code` | P0 |
| 9 | 1398 | `_reset_skin_options` | `status.reset` | success | success | P1 |
| 10 | 1429 | `_save_layout` | `_human_error` | error | error + `code` | P0 |
| 11 | 1432 | `_save_layout` | `status.failed`（通用） | error | error + `detail=str(exc)` | **P0** |
| 12 | 1436 | `_save_layout` | `status.layout_saved` | success | success | P1 |
| 13 | 1444 | `_apply_layout` | `status.layout_applied` | success | success | P1 |
| 14 | 1462 | `_delete_layout` | `status.layout_deleted` | success | success | P1 |
| 15 | 1479 | `_open_settings` | `msg_settings_unavailable` | info/warn | warn（可操作提示） | P2 |
| 16 | 1493 | `_rescan` | `status.failed` | error | error + `detail` | P0 |
| 17 | 1496 | `_rescan` | `msg_rescanned` | success | success | P1 |
| 18 | 1516 | `_do_import` | `_human_error` | error | error + `code` | P0 |
| 19 | 1521 | `_do_import` | `status.failed` | error | error + `detail` | P0 |
| 20 | 1527 | `_do_import` | `status.imported_converted` | warn | warn + `actions=(查看日志,)` | P1 |
| 21 | 1536 | `_do_import` | `msg_imported` | success | success | P1 |
| 22 | 1599 | `_on_error` | `_human_error(ErrorInfo)` | error | error + `code=error.code` | **P0** |

封装层删除项：`_set_status`(1563)、`_toast_offset`(1583)、`_forget_toast`(1588)、字段 `_toast`(436)。

### 4.2 静默缺口（应新增）

| # | 行 | 函数 | 现象 | 建议 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 1 | 1326–1333 | `_on_layer_toggled` | 置顶/普通层切换**完全无反馈**，而同组 `_on_desktop_toggled` 有 | 补 `success`（或统一都不弹，但要一致） | P1 |
| 2 | 1350–1352 | `_on_desktop_toggled` | 只在实际变更时提示，关闭桌面层无提示 | 对称补一条 | P2 |
| 3 | 1283 / 1293 | `_on_widget_toggled` / `_toggle_selected` | `_busy` 时静默 return | 保持（按钮已禁用），但需 `_busy` 覆盖到这些入口 | P2 |

### 4.3 托盘消息（跨通道规则）

| 位置 | 现状 | 判定 |
| --- | --- | --- |
| `plugin.py:299` | 快捷布局保存失败 → `ctx.tray.show_message(..., "warning")` | **保留**：托盘菜单可在窗口隐藏时触发，系统通知更合适 |
| `plugin.py:301` | 快捷布局已保存 → `ctx.tray.show_message` | **保留**，但需补规则：窗口可见时改 toast（避免"应用在前台却弹系统通知"） |

> 协议 §1.2 已把该规则写入：窗口可见 → toast；不可见 → tray。

### 4.4 其它

| 位置 | 现状 | 建议 |
| --- | --- | --- |
| `control/page.py:_set_busy` | `BusyStrip` 页内忙碌条 | 保留；导入/扫描这类长任务不应改成 toast |
| `plugin.py:173` | `report_error("PYRM_UNLOAD_FAILED", ...)` | 卸载期错误，保持日志（无 UI 可用） |
| `plugin.py:79` | `report = ctx.report_error` 注入存储层 | 保持；存储层错误由页面 `_on_error` 转 toast |

---

## 5. py-listen

### 5.1 `ui/tools_dialogs.py` — 15 个 `_toast` 调用点（设置页动作）

| # | 行 | 函数 | 文案键 | 场景 | 目标形态 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 78 | `_webdav_client` | `settings.webdav_invalid` | warn（校验） | `show(level="warn", channel="webdav")` | P0 |
| 2 | 96 | `test_webdav` | `settings.webdav_testing` | loading | `handle = loading(...)`，由 #3/#4 收敛 | **P0** |
| 3 | 102 | `test_webdav.done` | `settings.webdav_ok` | success | `handle.succeed(...)` | **P0** |
| 4 | 105 | `test_webdav.failed` | `settings.webdav_failed` | error | `handle.fail(..., detail=message)` | **P0** |
| 5 | 124 | `sync_backup` | `settings.webdav_syncing` | loading | `loading` + 收敛 | **P0** |
| 6 | 137 | `sync_backup.done` | 同步完成 | success | `handle.succeed` | P0 |
| 7 | 144 | `sync_backup.failed` | 同步失败 | error | `handle.fail` | P0 |
| 8 | 163 | `restore_backup` | `settings.webdav_restoring` | loading | `loading` + 收敛 | **P0** |
| 9 | 173 | `restore_webdav.done` | `settings.restore_failed`（`report.ok` 为假） | error | `handle.fail(..., detail=report.error)` | P0 |
| 10 | 182 | `restore_webdav.done` | `settings.restore_done` | success | `handle.succeed(...)` | P1 |
| 11 | 195 | `restore_webdav.failed` | `settings.webdav_restore_failed` | error | `handle.fail(..., detail=message)` | P1 |
| 12 | 574 | `export_backup` | `settings.backup_failed` | error | `show(level="error", detail=str(exc))` | P0 |
| 13 | 576 | `export_backup` | `settings.backup_done` | success | `show(level="success")` | P1 |
| 14 | 590 | `import_backup` | 导入失败 | error | 同 #12 | P0 |
| 15 | 599 | `import_backup` | 导入完成 | success | 同 #13 | P1 |

配套删除：`_TOAST_OFFSET = 58`(60)、`_ui_parent()`(63)、`offset` 分支(71)、`_toast()`(67)。

### 5.2 `ui/tools_dialogs.py` — 对话框内联状态（保留 + 局部升级）

| 行 | 内容 | 判定 |
| --- | --- | --- |
| 288 | `SourceManagerDialog._set_status`（页脚） | **保留**（对话框内就近反馈） |
| 314/377/391/395/400/406/427/447/463/481/507/516/519/524/528/534 | 音源导入/校验/删除进度与结果 | 保留页脚；**批量校验的最终结果**（528/534）建议补一条汇总 toast（`warn`/`success`），因为用户可能已关闭对话框 |

### 5.3 `ui/player_bar.py` — 播放提示

| 行 | 函数 | 现状 | 建议 | 优先级 |
| --- | --- | --- | --- | --- |
| 233 | `_on_playback_error` | `_show_toast(message, "danger")` | `show(level="error", channel="player", mode="replace", detail=...)` | P0 |
| 235–244 | `_show_play_notice` | resolving/buffering/remote → info toast | `show(level="info", channel="player", mode="replace", life=1500)`；如后续有"开始播放"事件，可升级为 `loading` → 自动收敛 | P1 |
| 246–256 | `_show_toast`（替换语义） | 手写 `dismiss(immediate)` 上一条 | 删除；用 `mode="replace"` | P0 |

### 5.4 `ui/online_page.py` — 12 个调用点（7 组结果，含重复上报）

| 行 | 函数 | 现状 | 问题 | 建议 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 1484/1485 | `_download` | `_set_status` + `_toast` 同文案 | **双份重复** | 只留 toast；`status_label` 用于列表级状态 | P1 |
| 1489/1490 | `_download.resolve_failed` | 同上 | 重复 + 异常串进正文 | toast `error` + `detail=payload` | P0 |
| 1499/1500 | `_download.add_failed` | 同上 | 重复 | 同上 | P0 |
| 1502/1503 | `_download.queued` | 同上 | 重复 | 只留 toast（success） | P1 |
| 1388 | `_play_from` 无音源 | `_set_status` | 无 toast（用户点了播放没反应） | `warn` + 指引"先导入音源" | **P0** |
| 1455 | `_add_later` | `_set_status` | 无 toast | `success`/`neutral` | P1 |
| 1463/1475 | 收藏/取消收藏 | `_set_status` | 无 toast | `success` | P2 |
| 1603 | `_set_status` | 页脚标签 | 保留（列表上下文） | — | — |

### 5.5 `ui/library_page.py` — 19 个 `status_label.setText`

| 类别 | 行 | 建议 |
| --- | --- | --- |
| **结果/错误 → 改 toast**（13） | 330（稍后播放）、389/392（收藏）、508（未配置 WebDAV）、571（扫描失败）、592（非法地址）、643（下载完成）、649（下载失败）、658（路径不存在）、691（自动同步完成汇总）、715/724（扫描完成/失败）、790（任务失败） | `ctx.toast.show(...)`；标签保留可，但不再是唯一出口 |
| **进度/持续状态 → 保留内联**（4） | 670（自动同步中）、741（监听告警）、775（已添加数）、805（忙碌文案） | 目录监听/进度属"持续状态"；若坚持用 toast 必须 `dedupe="suppress"` 否则刷屏 |
| **清空占位 → 保留**（2） | 304、778 | 仅重置标签，不是反馈 |

> **重点风险**：`_on_watch_changed` → `_scan_local_list(auto=True)` 由文件监听触发，
> 若把 670/691 改成 toast 将出现"每次文件变动弹一条"。必须走 `dedupe` + 低频汇总。

### 5.6 其它文件

| 文件:行 | 现象 | 建议 | 优先级 |
| --- | --- | --- | --- |
| `ui/downloads_page.py:442` | 下载完成只写页脚 | 补 `success` toast（后台完成时用户可能不在该页） | P1 |
| `ui/downloads_page.py:451` | 下载失败只写页脚 | 补 `error` toast + `detail` | P0 |
| `ui/player_page.py:326` | 歌词匹配"正在请求…" | 保留（页面内上下文） | — |
| `ui/player_page.py:360` | `report_error("PYLISTEN_ONLINE_FAILED")` | 补 `warn` toast（当前只有日志） | P1 |
| `ui/queue_page.py:374` | 清空队列成功无反馈 | 补 `success`（`neutral`） | P2 |
| `plugin.py:659/713/754/770/811` | 托盘/快捷键/状态广播失败只记日志 | 启动期降级 → 聚合一条 `warn`（"部分功能不可用，详情见日志"） | P2 |

---

## 6. 汇总统计

| 项目 | P0 | P1 | P2 | 改造小计 | 保留 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 基座 SllkGui | 4 | 14 | 2 | **20** | 2 组（7 个站点） | 另 7 项渲染器增强 |
| py-rm | 10 | 12 | 3 | **25** | 5 组 | 22 条来自同一封装 |
| py-listen | 20 | 21 | 3 | **44** | 9 组 | 15 条来自 `_toast`、13 条来自 `status_label` |
| **合计** | **34** | **47** | **8** | **89** | **16 组** | 7 项渲染器增强 |

按"改造单位"看（一次改动覆盖一组条目）：

| 改造单位 | 覆盖条目 | 级别 |
| --- | --- | --- |
| `guicore/feedback/toast_bus.py` + `CToast` 扩展 | 全部条目的运行时基础 | P0 |
| `gallery/api.py` + `gallery/toast.py` + 组合根绑定 | 插件侧能力 | P0 |
| `plugin_store.set_status` → `toast_bus` | 12 | P1 |
| `registry.py` 静默分支 | 6 个失败分支 | P0 |
| py-rm `_set_status` | 22 | P0/P1 |
| py-listen `_toast` | 15 | P0/P1 |
| py-listen `_show_toast` | 2 | P0 |
| py-listen `status_label` 收敛 | 13 | P1 |
| 静默入口补齐 | 12 | P0/P1/P2 |


---

## 7. 遗漏风险

| ID | 风险 | 触发条件 | 影响 | 缓解 |
| --- | --- | --- | --- | --- |
| R-01 | **静默失败**：页面/路由构建失败只写日志 | 插件 Surface 抛错、`impl` 缺失、返回非 QWidget | 用户"点了没反应"，问题只在日志里 | `registry.py` 6 个分支收敛为错误码 + 一条 error toast（P0） |
| R-02 | **锚点绑页面**：toast 随页面销毁 | 用户点完操作立刻切页（py-rm 现状） | 结果提示丢失，用户重复操作 | 锚点统一到顶层窗口（协议 §3.2） |
| R-03 | **偏移漂移**：三处各自计算顶部偏移 | 标题栏高度、页面头部布局调整 | toast 压住标题栏或悬空 | 偏移由 host 统一计算（删除 3 处本地实现） |
| R-04 | **重复提示**：同文案同时进页脚与 toast | py-listen `online_page` 4 处 | 视觉噪音，用户以为是两条事件 | 明确分工：页脚=列表级状态，toast=动作结果 |
| R-05 | **提示风暴**：轮询/文件监听逐次弹 | 目录监听、WebDAV 轮询、进度回调误用 show | 刷屏、掉帧、限流后信息全丢 | `dedupe` + `mode=replace` + 限流（20 次/2s） |
| R-06 | **常驻泄漏**：`life=0` 未收敛 | 异常分支提前 return | 加载条永久停留，遮住后续提示 | 配对规则 + 120s 看门狗 + 卸载清理 |
| R-07 | **忙碌期静默**：`_busy` 早退 | 用户连点 | 无反馈但也没报错 | 按钮禁用是主手段；不额外弹 toast（避免噪音），但要保证禁用态明显 |
| R-08 | **线程误用**：worker 里直接改控件 | 插件自行起线程 | 随机崩溃 / 界面错乱 | 协议层跨线程自动排队；文档禁止直接操作控件 |
| R-09 | **级别拼写漂移**：`warning`/`danger`/`critical` 混用 | 各插件历史写法 | 严格实现会抛 `ValueError` 打断业务 | 别名表 + 兜底 `info` + 严格模式仅在测试开启 |
| R-10 | **热重载悬空**：卸载后回调仍持有页面引用 | 更新/停用插件瞬间有 toast 在计时 | `RuntimeError: Internal C++ object already deleted` | `PLUGIN_UNLOADED` 拦截 + 句柄弱引用 + 加载器统一 `clear_plugin` |
| R-11 | **跨窗口错位**：设置窗口动作的 toast 落到主窗口 | py-listen 用 `activeWindow()` 的时序差异 | 提示被设置窗口遮挡，用户以为没生效 | `anchor=AUTO` 优先活动模态窗口 |
| R-12 | **托盘/toast 混用**：窗口可见时弹系统通知 | py-rm 快捷布局、未来下载完成通知 | 体验割裂；系统通知可能被勿扰模式吞掉 | 规则写入协议 §1.2；新增统一 `notify` 辅助（P2） |
| R-13 | **文案不可定位**：通用"操作未能完成" | `_fail` 丢 `error_code` | 用户无法自查，支持成本高 | `ToastCatalog` 按码给文案 + `actions=(查看日志,)` |
| R-14 | **长文本撑屏**：340px 宽卡片 + 长异常串 | 直接把 `str(exc)` 拼进正文 | 单条 toast 占半屏 | 正文 500 字符上限 + `detail` 分流 |
| R-15 | **假进度**：`restore_webdav.done` 在 GUI 线程同步执行 `import_backup` | 备份较大（数千首） | 界面冻结，"正在读取远程备份…"看似卡死 | 导入移到 worker；toast 用 `loading` → `progress` → 结果三段；本项与协议改造同批处理 |

---

## 8. 测试关注点

### 8.1 基座

| 测试 | 断言 | 方法 |
| --- | --- | --- |
| `test_toast_router_no_qt` | `import sllkgui.gallery.toast` 不加载 PySide6 | `sys.modules` 断言 |
| `test_toast_level_alias` | `danger`/`warning`/`critical` → 正确级别；非法值 → `info` + `TOAST_INVALID_LEVEL` | `ToastRouter` + `RecordingHost` |
| `test_toast_dedupe_policies` | 4 种策略的条数与 `repeat` | 同上，注入假时钟 |
| `test_toast_overflow_eviction` | 5 info + 1 error → error 保留，被挤者收到 `SUPERSEDED` | 同上 |
| `test_toast_replace_channel` | 同通道连发 3 条 → 仅 1 条，前两条 `REPLACED` | `qtbot` + 假渲染器 |
| `test_toast_cross_thread_order` | worker 线程连发 10 条 → 顺序与调用一致 | `QThread` + 队列等待 |
| `test_toast_anchor_survives_page_switch` | 页面销毁后 toast 仍在（锚点为窗口） | `qtbot` + 切换 `QStackedWidget` |
| `test_toast_plugin_unload_cleanup` | 卸载后 `update()` 返回 `TOAST_PLUGIN_UNLOADED`，无异常 | `PluginToast` 直测 |
| `test_toast_leak_watchdog` | 注入短超时 → 持久条自动关闭，`reason=failed` | 同上 |
| `test_plugin_store_failure_has_code` | `_fail("GIT_TIMEOUT", ...)` 的 toast 含码与"查看日志" | spy `toast_bus().show` |
| `test_surface_build_failure_visible` | `ensure_registered_page` 失败 → 一条 error toast | 现有 `test_gallery_failure_visibility.py` 扩展 |
| `test_toast_component_regression` | 旧 `CToast.show_message` 堆叠/`clear`/`closed` 不变 | 现有 `test_feedback_components.py`、`test_toast_interaction.py` |

### 8.2 py-rm

| 测试 | 断言 |
| --- | --- |
| 状态替换 | 连续 3 次切换小部件 → 仅 1 条 toast，文案为最后一次 |
| 错误码透传 | `PyrmError` → toast `code` 等于 `exc.code`，正文不含异常类名 |
| 导入告警 | Rainmeter 转换告警 → `warn` + `repeat` 语义正确 |
| 切页保持 | 触发"已启用「时钟」"后切到插件管理 → toast 仍可见（锚点窗口化） |
| 层切换对称 | 置顶/普通层切换都有反馈（或都无），不得只覆盖一半 |

### 8.3 py-listen

| 测试 | 断言 |
| --- | --- |
| WebDAV 三步收敛 | test/sync/restore 各只产生 **1 条** toast，终态为 success 或 error |
| 播放提示不堆叠 | 快速切歌 5 次 → 通道内仅 1 条 |
| 播放失败可读 | 错误正文无堆栈；`detail` 含原始信息 |
| 下载完成提示 | 后台下载完成 → 出现 success toast（非当前页也可见） |
| 监听风暴抑制 | 模拟 20 次目录变更 → toast ≤2 条（去重/限流生效） |
| 设置窗口锚定 | 设置页触发动作 → toast 出现在设置窗口 |
| 页脚与 toast 分工 | 同一动作不出现"页脚 + toast"同文案两条 |

### 8.4 回归与门禁

```bash
# 基座
uv run pytest -q tests/test_feedback_components.py tests/test_toast_interaction.py \
               tests/test_gallery_failure_visibility.py tests/test_architecture_boundaries.py
uv run ruff check src tests && uv run mypy

# 分层守卫（新增 gallery/toast.py 后必须仍绿）
uv run pytest -q tests/test_architecture_boundaries.py
```

- **分层守卫**：`gallery/toast.py` 若 import PySide6 会拉高 CLI 启动成本，需新增一条守卫
  （参照 `appcore` 的"不 import PySide6"测试写法）。
- **视觉回归**：P1 不改外观，截图对比应与现状一致；P2 增加进度/按钮后需更新基线。
- **人工复测**（`MANUAL_QA` 口径）：连点刷新、切页后提示、设置窗口动作、断网错误、长时间 loading。

---

## 9. 实施顺序建议

| 阶段 | 范围 | 交付 | 验收 |
| --- | --- | --- | --- |
| **P0-1** | `gallery/api.py` 类型 + `gallery/toast.py` 路由 + `guicore/feedback/toast_bus.py` | ✅ 已完成 | `test_toast_protocol.py` / `test_toast_bus.py` |
| **P0-2** | `registry.py` 静默分支 + `gallery/window.py` + 插件管理页 `_fail` | ✅ 已完成 | `test_gallery_failure_visibility.py`（改为断言协议字段） |
| **P0-3** | py-rm `_set_status` → `ctx.toast`；py-listen `_toast` / `_show_toast` → `ctx.toast` | ✅ 已完成 | 两插件 grep 无 `CToast` 直调 |
| **P1** | 其余成功/警告点批量替换；py-listen 页脚与 toast 去重；loading 配对 | ✅ 已完成 | `test_skin_settings.py` 断言通道/替换；WebDAV 三流程同句柄 |
| **P2** | `CToast` 加载/进度/动作/计数；`ToastCatalog`；lint 规则；`notify` 辅助 | ✅ 已完成（`plugin_store/copy.py` 承担码表；lint 规则留待 4.2） | 视觉基线待人工复测 |

**不建议一次性全改**：先 P0-1/P0-2（基座自身），再逐插件替换。原因是协议一旦定稿，
插件侧只是机械替换；反过来先改插件会迫使他们继续维护私有封装。

---

## 附录：可复现的统计命令

```bash
# 各项目 toast 类调用点（AST，排除定义）
python - <<'PY'
import ast, pathlib
targets = {
 "SllkGui/src/sllkgui/guis/pages/plugin_store/page.py": {"set_status"},
 "py-rm/surfaces/control/page.py": {"_set_status"},
 "py-listen/ui/tools_dialogs.py": {"_toast"},
 "py-listen/ui/online_page.py": {"_toast", "_set_status"},
 "py-listen/ui/player_bar.py": {"_show_toast"},
}
for path, names in targets.items():
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    hits = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and (getattr(n.func, "attr", None) or getattr(n.func, "id", None)) in names]
    print(path, len(hits), hits)
PY

# 直接使用 CToast 的位置（应只剩基座内部与迁移中的封装层）
grep -rn "CToast" --include=*.py SllkGui/src py-rm py-listen | grep -v __pycache__ | grep -v ".venv"

# 硬编码顶部偏移
grep -rn "_TOAST_OFFSET\|_toast_offset" --include=*.py SllkGui/src py-rm py-listen
```
