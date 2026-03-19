# CustomGUI 完整架构版重构计划（6-8 周）

更新时间：2026-03-19

## 目标

1. 消除 GUI/GuiCore 双向耦合风险，明确分层边界。
2. 收敛历史兼容代码，统一到单一配置与资源访问入口。
3. 将主窗口从“集中控制器”拆分为可组合控制器。
4. 用自动化规则约束架构回退，保证长期可维护性。

## 目标分层（最终态）

1. `domain`：纯模型与协议（配置 schema、错误模型、插件协议、事件模型）。
2. `application`：业务用例编排（页面路由、主题切换、命令分发、启动流程）。
3. `infrastructure`：IO/外部依赖（YAML、文件系统、日志、遥测、硬件接口）。
4. `presentation`：PySide6 窗口与组件（GUI、GuiCore）。

## 执行路线

### Phase A（第 1-2 周）：边界收敛与旧入口冻结

1. 清点并冻结历史入口（先做兼容转发，不直接删除）。
2. 标记弃用接口（DeprecationWarning + 文档说明）。
3. 建立分层依赖约束（先测试/脚本校验，再逐步强约束）。
4. 抽离资源定位公共服务，消除 `os.getcwd()` 依赖。

交付物：

1. 旧入口冻结清单与兼容映射表。
2. 架构依赖约束基线测试。
3. 统一资源定位器初版。

### Phase B（第 3-4 周）：主窗口拆分与用例化

1. 拆分 `main.py` 交互责任：`PageRouter`、`ThemeController`、`ColumnController`、`TitleBarController`。
2. 将页面切换与菜单动作转为应用层用例，不在窗口类里直接拼装业务逻辑。
3. 为关键交互增加集成测试（按钮 -> 路由 -> 页面）。

交付物：

1. 主窗口控制器化改造。
2. 路由与列显隐集成测试。
3. 回归基线（pytest + lint）通过。

### Phase C（第 5-6 周）：插件生命周期与隔离

1. 补齐插件生命周期：发现、加载、启停、卸载。
2. 插件异常隔离：单插件失败不影响主流程。
3. 插件版本兼容检查（协议版本字段 + 校验）。

交付物：

1. 插件生命周期管理器。
2. 插件容错与兼容测试。
3. 插件开发文档。

### Phase D（第 7-8 周）：收口与迁移完成

1. 删除已冻结且无调用的历史入口。
2. 命名一致性修复（拼写与文件名历史包袱）。
3. 文档、CI 门禁、发布流程与新架构对齐。

交付物：

1. 迁移完成报告与风险清单。
2. 架构文档更新。
3. 发布前检查清单升级。

## 风险与回滚

1. 风险：大量重命名引发导入链抖动。
	回滚：保留兼容 re-export 层一个版本周期。
2. 风险：UI 事件链重构导致行为回归。
	回滚：先并行保留旧 handler，灰度切换。
3. 风险：插件协议升级破坏现有插件。
	回滚：协议版本适配器 + 明确 deprecate 周期。

## 第一批任务（当前执行）

- [x] 第一步：冻结历史配置入口 `AppCore.SYS.module.config_module`，改为兼容转发到 `AppCore.SYS.other.folder_tools.AppSettings`，并发出弃用警告。
- [x] 第二步：新增架构依赖约束测试（禁止 presentation 反向依赖 application/domain 细节实现）。
- [x] 第三步：引入统一资源定位器，逐步替换 `os.getcwd()` 路径拼接。

## 执行记录

2026-03-19：已将 `config_module.py` 从“独立配置加载实现”改为“冻结兼容层”，统一转发到 `get_app_context().settings`，并保留旧 API（`find_settings` / `AppSettings`）以避免破坏历史调用。
2026-03-19：已新增 `tests/test_architecture_boundaries.py` 作为架构门禁，约束 `AppCore` 不依赖 `GUI/GuiCore`，并约束 `GUI/GuiCore` 不直接导入 `AppCore.SYS` 内部实现；同时将 `loading_window/functions.py` 改为仅使用 `AppCore` 公共导出，并接入 CI 工作流执行该测试。
2026-03-19：已新增 `resource_locator.py` 统一资源根目录解析，替换 `static_func.py`、`folder_tools.py`、`left_menu/menu_button.py` 中 `os.getcwd()` 路径拼接；新增 `tests/test_resource_locator.py` 验证在切换工作目录后资源解析仍正常。
2026-03-19：已新增 `tests/test_no_cwd_runtime_dependency.py`，对 `AppCore/GUI/GuiCore/main.py` 建立 `os.getcwd()` 禁用门禁，并接入 CI，防止后续路径解析回退到 cwd 依赖。
2026-03-19：Phase B 第一步已启动并完成第一刀：新增 `GUI/windows/main_window/controller.py`（`MainWindowController`），将 `main.py` 中按钮路由、页面切换、主题切换与侧栏交互迁移至控制器，主窗口类仅保留生命周期与事件入口。
2026-03-19：Phase B 第二刀完成：`MainWindowController` 进一步拆分为 `PageRouterController`、`ThemeController`、`ColumnController`，并新增 `tests/test_main_window_controller.py` 覆盖页面切换、主题轮换与插件命令分发行为。
2026-03-19：已引入应用层用例 `AppCore/APP/main_window_use_cases.py`（`MainWindowButtonUseCase`），将按钮分发决策从控制器下沉为纯逻辑；控制器改为编排执行，新增 `tests/test_main_window_use_cases.py` 覆盖决策规则。
2026-03-19：已新增 `tests/test_main_window_integration.py`，覆盖“按钮 -> 路由/动作/插件命令”关键交互链路，并在 CI 增加 Main window interaction tests 专项步骤，完成 Phase B 第 3 项（关键交互测试闭环）。
2026-03-19：Phase C 第一刀完成：`plugin_module.py` 增加协议版本校验（`protocol_version`）、生命周期控制（`enable/disable/unregister`）、批量加载（`load_plugins`）与故障隔离（页面加载与命令执行失败写入 `load_errors` 且不中断流程）；`tests/test_plugin_protocol.py` 已补齐对应覆盖。
2026-03-19：Phase C 第二刀完成：插件发现机制已支持从 `plugins.yml` 读取模块路径并动态加载（`discover_plugin_modules` / `load_plugins_from_modules` / `discover_and_load_plugins`），补齐协议兼容矩阵辅助接口（`supported_protocol_versions` / `is_protocol_supported`）与对应测试，并在 CI 增加 Plugin lifecycle tests 步骤。
2026-03-19：Phase C 第三刀完成：插件协议迁移能力已落地（`register_protocol_adapter` + 自适配加载），旧协议插件可在注册阶段自动转换为受支持协议；补充适配成功与适配失败边界测试，形成“校验 + 迁移 + 隔离”闭环。
2026-03-19：Phase D 命名一致性第一批完成：新增规范入口 `language_module.py` 与 `loading_window/ui_main.py`，包导出改为优先使用规范命名，同时保留历史拼写模块兼容；新增 `tests/test_naming_consistency.py` 与 CI 门禁，防止默认导入回退到历史拼写。
2026-03-19：Phase D 第二批完成：新增 `docs/LEGACY_COMPATIBILITY.md` 梳理历史兼容入口与迁移窗口策略；新增 `tests/test_legacy_import_policy.py` 并接入 CI，禁止运行时代码新增对 `config_module/languge_module/ui_mian` 的依赖。
2026-03-19：Phase D 第三批试点完成：已移除低风险历史入口 `AppCore.SYS.module.languge_module`，`language_module.py` 转为真实实现并更新测试与兼容清单；其余旧入口（`config_module`、`ui_mian`）继续按窗口策略保留。
2026-03-19：Phase D 第四批试点完成：已移除低风险历史入口 `GUI.windows.loading_window.ui_mian`，`ui_main.py` 转为真实实现并更新命名一致性测试、兼容清单与策略门禁；当前仅保留 `config_module` 作为历史兼容入口。
2026-03-19：Phase D 第五批收口完成：已移除最后一个历史兼容入口 `AppCore.SYS.module.config_module`，并将兼容测试改为“旧入口已移除”断言；`docs/LEGACY_COMPATIBILITY.md` 更新为“当前无遗留入口”。
2026-03-19：结项收尾完成：README 已补齐迁移状态与发布前门禁说明，文档索引新增 Legacy Compatibility 入口；最终状态通过全量测试与文档生成校验。
