# 变更规划与追溯

> 基线：SllkGUI `1.0.0` / tag `base-v1.0.0`，代码基线 `main`（`c6bc018`），日期 2026-11-09。
> 记录约定：本文件是**一次性规划矩阵**，只以表格与稳定编号归档结论，不记录过程、不维护待办清单；结论合入 `CHANGELOG.md` / `docs/ARCHITECTURE.md` / `docs/MANUAL_QA.md` 后归档。
> 编号：`FIX-01`..`FIX-12` 为本轮修复主键，`EXT-01`..`EXT-12` 为扩展项主键；编号一经分配不再变更，各节以「编号」为主键互相引用，并落到 commit message 与新增测试注释。刻意不复用 `docs/MANUAL_QA.md` 的 `F-xx` / `A-xx` / `ENV-xx` 编号。
> 状态：`计划中` / `已修复` / `作废`；各节状态列在归档时统一收口，逐批进度以 §7 变更追溯为准。
> 阶段：`S1` = 本轮 B1–B7；`S2`–`S4` 仅为后续分期代号，不产生本轮代码改动。
> 实测基线：525 用例 / 524 passed / 1 skipped；行覆盖 72%，212 个模块中 21 个低于 50%。
> 本轮决策：P0 + P1 共 12 项全部修复；P2/P3 只登记为扩展项，零代码改动；允许修正带来的行为变更并同步文档；分 7 批提交后推送。

---

## 1. 问题摘要

| 编号 | 级别 | 模块 / 文件 | 现象 | 代码线索 | 状态 |
| --- | --- | --- | --- | --- | --- |
| FIX-01 | P0 | `src/sllkgui/cli.py` | `install-demo --force` 直接删除同名目录，无来源校验、无非空检查、无符号链接判断；目标等于源目录时自毁内置示例 | `cli.py:84-96` | 计划中 |
| FIX-02 | P0 | `src/sllkgui/appcore/user_settings.py` | 高版本 `user.yaml` 读取时告警「不覆盖未知数据」，回写却只留白名单字段并把版本降级；迁移函数为空；临时文件名固定且无 `fsync` | `user_settings.py:133-157` `160-170` `220-240` | 计划中 |
| FIX-03 | P0 | `src/sllkgui/cli.py` | `doctor --apps-dir` 会 `exec_module` 任意目录下的插件代码；加载失败仍返回 0；外部路径无归属校验 | `cli.py:165-208` `guis/app_namespace.py:116` | 计划中 |
| FIX-04 | P0 | `.workflow/ReleasePipeline.yml` | 流水线只认 `v*` tag，而发版文档用 `base-v*`；两条流水线门禁命令集不一致（发布侧无 mypy、无覆盖率、ruff 范围小） | `ReleasePipeline.yml:40-44` `76-77` `QualityGate.yml:57-62` | 计划中 |
| FIX-05 | P1 | `appcore/sysx/config/paths.py` | `program_root()` 兜底 `Path.cwd()`，日志与配置可能随启动目录漂移；`logger_module` 导入期即建目录；三份扫描守卫无「扫到东西」自检且漏检 `Path.cwd()` | `paths.py:213` `logger_module.py:57-61` `tests/test_architecture_boundaries.py:14-19` | 已修复 |
| FIX-06 | P1 | `src/sllkgui/config.py` | `ConfigAlreadyLoadedError` 只在 `_CONFIGURED` 为真时检查，首次 `configure()` 在上下文已加载后静默失效；`None` 保留历史值、`env_fallback` 被默认值覆盖；`apps_root` 与遥测绕过配置直读环境变量 | `config.py:141-186` `paths.py:173-178` `telemetry_module.py:34` | 计划中 |
| FIX-07 | P1 | `appcore/sysx/modules/theme_module.py` | `unsubscribe` 用 `is` 比较 `WeakMethod()` 结果恒 False；失效引用只跳过不清理；`apply()` 与 `ColorPalette.update()` 无锁；`ConfigContext.load` 逐字段赋值而读侧无锁 | `theme_module.py:132-177` `color_module.py:45-48` `config/registry.py:190-292` | 计划中 |
| FIX-08 | P1 | `appcore/sysx/modules/error_module.py` | `@dataclass` 继承 `Exception` 导致 `args=()`；配置注册表只接 `ValueError` 漏 `IOErrorBoundary`；`events.jsonl` 无轮转、遥测只接 `OSError` | `error_module.py:4-13` `config/registry.py:139` `telemetry_module.py:77-127` | 计划中 |
| FIX-09 | P1 | `src/sllkgui/guis/app_loader.py` | `reset_apps_cache()` 不清全局 `PluginRegistry`，重载触发 `PLUGIN_DUPLICATE_MENU`；先注册菜单再执行入口，失败留孤儿菜单；`exec_module` 失败不回滚 `sys.modules` | `app_loader.py:120-155` `291-295` `app_namespace.py:116` | 计划中 |
| FIX-10 | P1 | `src/sllkgui/config.py` | `strict_plugins` 全库零读取点，三处文档语义互相矛盾，用户误以为启用了启动期失败门禁 | `config.py:44` `133` `160` `README.md:286` `PLUGIN.md:13` `API.md:32` | 计划中 |
| FIX-11 | P1 | `src/sllkgui/guis/language_service.py` | `_retranslate_pages` 要求 `retranslate()`，而全库只有 uic 的 `retranslateUi()` 且页面栈含两个占位页，局部刷新恒不可达；刷新失败仍无条件写 `user.yaml`；`ctx.language` 回落静态配置值；v2 两个生命周期钩子零调用点 | `language_service.py:45-55` `90-117` `app_context.py:45-50` `app_protocol.py:136` `143` | 计划中 |
| FIX-12 | P1 | `src/sllkgui/guis/app_manifest.py` | 缺 `app_name` 的回退值未写回 config，图标解析与页面注册读到两套名字；`bool("false")` 为真；重复 `button_id` 静默 last-wins；`test_page_registry.py:10` 断言恒真 | `app_manifest.py:147-159` `app_loader.py:112-140` `plugin_module.py:345-354` | 计划中 |

## 2. 影响范围

| 编号 | 影响面 | 对外行为变化 | 文档同步点 | 破坏性 | 状态 |
| --- | --- | --- | --- | --- | --- |
| FIX-01 | `install-demo` 调用方、数据目录 | 相交/符号链接/复制失败时拒绝并返回非 0 | `README.md` `CHANGELOG.md` | 否 | 计划中 |
| FIX-02 | 用户偏好持久化、版本升降级 | 高版本文件不再降级版本或丢未知字段；`fsync` 失败可观测 | `docs/API.md` `CHANGELOG.md` | 否 | 计划中 |
| FIX-03 | `doctor` 调用方、CI 健康脚本 | 默认不执行插件代码、越界目录被拒、失败返回非 0；新增 `--load` / `--allow-external` | `README.md` `PLUGIN.md` `API.md` `MANUAL_QA.md` `contributing.md` `CHANGELOG.md` | 否（行为变更） | 计划中 |
| FIX-04 | 发版流水线、贡献者发版流程 | `base-v*` 触发发布；发布侧新增 mypy、全仓 ruff、覆盖率 70% 门禁 | `contributing.md` `CHANGELOG.md` `README.md` `ARCHITECTURE.md` | 否 | 计划中 |
| FIX-05 | 日志/遥测/用户配置落盘位置 | 不再回落 cwd，日志目录不在导入期创建 | `docs/ARCHITECTURE.md` `CHANGELOG.md` | 否 | 已修复 |
| FIX-06 | 所有 `configure()` 宿主、沙箱与测试隔离 | 首次 `configure` 在上下文已加载后也抛错；`env_fallback=False` 真正生效 | `docs/API.md` `README.md` `ARCHITECTURE.md` `CHANGELOG.md` 破坏性表 | **建议登记** | 计划中 |
| FIX-07 | 主题热切换、自绘组件重绘 | 退订生效、失效订阅被清理、读写加锁 | `docs/ARCHITECTURE.md` | 否 | 计划中 |
| FIX-08 | 领域异常、配置加载、诊断事件 | `AppError.args` 非空；坏 YAML 转 `IOErrorBoundary`；事件文件轮转 | `docs/API.md` `ARCHITECTURE.md` | 否 | 计划中 |
| FIX-09 | 应用热重载、测试隔离、坏插件容错 | 重载幂等；失败应用不留菜单与模块残留 | `docs/PLUGIN.md` `CHANGELOG.md` | 否（行为变更） | 计划中 |
| FIX-10 | `configure()` 公开 API | 移除 `strict_plugins` 参数与字段 | `docs/API.md` `README.md` `PLUGIN.md` `CHANGELOG.md` 破坏性表 | **是** | 计划中 |
| FIX-11 | 语言切换、应用上下文、v2 插件 | 失败时回滚不落盘；`ctx.language` 跟随当前语言；`retranslateUi` 生效；钩子被调用 | `docs/PLUGIN.md` `API.md` `MANUAL_QA.md` `CHANGELOG.md` | 否（行为变更） | 计划中 |
| FIX-12 | 应用清单、页面路由 | 布尔字段严格解析；缺 `app_name` 写回；重复 `button_id` 显式报错 | `docs/PLUGIN.md` `CHANGELOG.md` | 否（行为变更） | 计划中 |

## 3. 修复项

| 编号 | 对应问题 | 最小改动点 | 复现测试名 | 批次 | 状态 |
| --- | --- | --- | --- | --- | --- |
| FIX-01 | P0-1 | `_cmd_install_demo` 加 source/dest 相交校验、`is_symlink()` 拒绝、`OSError` 捕获与非 0 退出 | `test_install_demo_force_rejects_source_dest_overlap` 等 3 条 | B2 | 计划中 |
| FIX-02 | P0-2 | 回写保留原 `schema_version` 与未知键；补迁移分支；`mkstemp` 唯一临时文件 + `fsync` | `test_future_schema_version_roundtrip_preserves_version_and_unknown` 等 3 条 | B3 | 计划中 |
| FIX-03 | P0-3 | `doctor` 默认只发现不加载、新增 `--load`；`--apps-dir` 归属校验与 `--allow-external`；失败非 0；修正 docstring | `test_doctor_does_not_execute_plugin_code_by_default` 等 4 条 | B2 | 计划中 |
| FIX-04 | P0-4 | `prefix: [v]` → `[base-v]`；发布侧对齐全仓 ruff / mypy / 覆盖率门禁 | 两 yml 命令集静态核对 | B7 | 计划中 |
| FIX-05 | P1-1 | `program_root()` 兜底改 `sys.executable` 目录；Logger 惰性初始化；三份扫描守卫补自检与 `Path.cwd()` 匹配 | `test_program_root_stable_without_data_dir` `test_runtime_code_must_not_use_path_cwd` 等 4 条 | B1 | 已修复 |
| FIX-06 | P1-2 | `configure()` 检查条件改为上下文已加载即抛错；`env_fallback` 用 `None` 哨兵保留历史值；`apps_root`/遥测统一走解析 helper | `test_configure_after_context_loaded_raises_on_first_call` 等 4 条 | B4 | 计划中 |
| FIX-07 | P1-3 | `==` 比较与失效引用清理；`RLock` 或锁内快照；`ConfigContext` 一次性发布快照 | `test_unsubscribe_removes_bound_method` 等 3 条 | B3 | 计划中 |
| FIX-08 | P1-4 | 显式 `__init__` 调 `Exception.__init__`（`__str__` 输出不变）；补 `IOErrorBoundary` 捕获；事件轮转与序列化异常兜底 | `test_app_error_args_are_populated` 等 3 条 | B3 | 计划中 |
| FIX-09 | P1-5 | 记录本轮 plugin_id 定向清理（禁止整体 reset）；菜单注册后置或失败回滚；`sys.modules.pop` | `test_reset_apps_cache_reload_has_no_duplicate_menu` 等 3 条 | B5 | 计划中 |
| FIX-10 | P1-6 | 删除字段/参数/赋值与 3 处文档；CHANGELOG 登记迁移方式 | `test_configure_has_no_strict_plugins_param` | B4 | 计划中 |
| FIX-11 | P1-7 | `retranslateUi` 适配层并跳过占位页；刷新成功才落盘、失败回滚；`ctx.language` 取 `Language.current()`；补钩子调用点 | `test_retranslate_pages_uses_retranslateui_adapter` 等 3 条 | B6 | 计划中 |
| FIX-12 | P1-8 | 回退值写回 config；统一 `_as_bool()`；`build_page_routes` 重复 ID 抛错；先重写恒真断言 | `test_registry_button_ids_unique`（重写）等 4 条 | B5 | 计划中 |

## 4. 扩展项

> 本节只登记规划，**本轮零代码、零配置改动**；状态一律「计划中」，触发条件写清前置依赖。

| 编号 | 分期 | 主题 | 涉及文件（本轮不改） | 触发条件 | 状态 |
| --- | --- | --- | --- | --- | --- |
| EXT-01 | S2 | 插件进程隔离与沙箱（当前 `PLUGIN.md:6-14` 明确「不是沙箱」） | `docs/PLUGIN.md` `guis/app_loader.py` `guis/app_namespace.py` | 出现不可信插件需求 | 计划中 |
| EXT-02 | S2 | `events.jsonl` 完整轮转策略与指标压缩归档 | `appcore/sysx/modules/telemetry_module.py` | 长驻进程 / 诊断数据膨胀 | 计划中 |
| EXT-03 | S2 | `_ContextView` 全量读写锁与 `ConfigContext` 快照发布的并发压测 | `appcore/sysx/config/registry.py` | 引入多线程配置写入 | 计划中 |
| EXT-04 | S2 | 主题 `apply` / `_notify` 全链路 `RLock` 并发测试 | `appcore/sysx/modules/theme_module.py` | 后台线程触发主题切换 | 计划中 |
| EXT-05 | S3 | 移除协议 v1（`PAGE` / `build_page` / `register_plugins`）兼容壳 | `guis/app_loader.py` `docs/PLUGIN.md` `ARCHITECTURE.md:222-224` | 下一个 major 版本 | 计划中 |
| EXT-06 | S3 | 清理 `CLineEdit` / `CPushButton` 兼容壳与旧 `resource/` 布局 | `guicore/` `ARCHITECTURE.md:222-224` | 下一个 major 版本 | 计划中 |
| EXT-07 | S3 | 清理遗留文档引用与 `appcore/tool/Net.py` 历史命名 | `docs/contributing.md:63` `81-82` | 下一次文档整理 | 计划中 |
| EXT-08 | S4 | 统一 `v*` / `base-v*` tag 体系并清理历史 tag（需远端管理员、不可逆） | `.workflow/ReleasePipeline.yml` `CHANGELOG.md` | 发布流程重构 | 计划中 |
| EXT-09 | S4 | MANUAL_QA 语言切换状态保留与排序选中项产品确认 | `docs/MANUAL_QA.md:452-453` | 产品确认结论 | 计划中 |
| EXT-10 | S4 | MANUAL_QA 遗留视觉缺陷与 `paintEvent` 性能优化 | `docs/MANUAL_QA.md` `guicore/` | 视觉基线复核 | 计划中 |
| EXT-11 | S4 | Win32 亚克力开关、Win10/RDP 回退、多显示器、高 DPI 人工验收矩阵 | `docs/MANUAL_QA.md:468-475` | Windows 真机发布前 | 计划中 |
| EXT-12 | S4 | `appcore` 去 Qt 依赖 / 轻量 doctor、PyInstaller 冻结形态端到端验证、PyPI 发布路径 | `appcore/sysx/common/static_func.py` `src/sllkgui/window.py` `scripts/build_package.py` | 跨平台与正式发布 | 计划中 |

## 5. 优先级与顺序

| 编号 | 批次 | 前置依赖 | 合入顺序 | 分组理由 | 状态 |
| --- | --- | --- | --- | --- | --- |
| FIX-05 | B1 | 无 | 1 | 规则与源码必须同批，否则新增 `Path.cwd()` 守卫立刻红；规划矩阵须首批建立以固定 ID | 已修复 |
| FIX-01 FIX-03 | B2 | 无 | 2 | 同改 `cli.py` 与 `test_cli.py` 的退出码断言 | 计划中 |
| FIX-02 FIX-07 FIX-08 | B3 | 无 | 3 | 共享 `config/registry.py`；`AppError.__str__` 契约与 4 处 `match=CODE` 断言须同批 | 计划中 |
| FIX-06 FIX-10 | B4 | B1 B3 | 4 | 公开 API 签名与破坏性参数，独占一批便于评审回滚 | 计划中 |
| FIX-09 FIX-12 | B5 | 无 | 5 | 共享 `app_loader.py` / `plugin_module.py`；恒真断言须先重写 | 计划中 |
| FIX-11 | B6 | B5 | 6 | 语言重建走 `load_registered_pages`，依赖重载幂等 | 计划中 |
| FIX-04 | B7 | B2–B6 | 7 | 门禁对齐后发布流水线首次跑 mypy/覆盖率，须最后合入并做归档收尾 | 计划中 |

优先级判据：能造成数据丢失或突破信任边界的先于功能缺陷；让质量信号可信先于增加更多测试；抽象重构放到正确性收敛之后。

## 6. 验收标准

**每批必跑**：`uv run ruff check src tests apps examples scripts`、`uv run mypy`、`uv run pytest --cov=sllkgui --cov-report=term-missing --cov-fail-under=70`、本批专项 pytest、`git status --porcelain`（前后各一次，须为空）、`git diff --check`。
**收尾加验**：`uv build --wheel`、`uv run twine check dist/*.whl`、`uv run python scripts/wheel_smoke.py`。
**人工验收**（登记 EXT-11 / EXT-12）：Win32 亚克力与 RDP 回退、多显示器、高 DPI、PyInstaller 冻结形态、`base-v*` tag 首次触发发布流水线。

| 编号 | 测试名 / 命令 | 通过判据 | 人工验收项 | 状态 |
| --- | --- | --- | --- | --- |
| FIX-01 | `pytest -q tests/test_cli.py -k force` | 相交·符号链接·复制失败均非 0 且目标未被破坏；既有 3 条用例保持绿 | 源码树默认 `--force` 路径 | 计划中 |
| FIX-02 | `pytest -q tests/test_user_settings.py` | `schema_version: 99` 回写后仍为 99、未知键保留；`fsync` 被调用 | 版本降级再升级 | 计划中 |
| FIX-03 | `pytest -q tests/test_cli.py` + `sllkgui doctor` | 插件副作用不触发；越界被拒；失败非 0；`import sllkgui.cli` 后无 PySide6 | 干净环境诊断输出 | 计划中 |
| FIX-04 | 两 yml 命令集静态核对 + `uv build --wheel` | `prefix: [base-v]`；发布侧含全仓 ruff / mypy / 覆盖率 70；未删任何 tag | `base-v*` 首次触发 | 计划中 |
| FIX-05 | `pytest -q tests/test_no_cwd_runtime_dependency.py tests/test_architecture_boundaries.py tests/test_legacy_import_policy.py` | `Path.cwd()` 零命中；三份扫描器各扫到 >0 文件；`program_root()` 与 cwd 无关 | wheel/frozen 形态日志落点 | 已修复 |
| FIX-06 | `pytest -q tests/test_path_resolution.py tests/test_config_framework.py` + `mypy` | 首次 `configure` 抛 `ConfigAlreadyLoadedError`；`env_fallback=False` 时 3 处环境变量全失效 | 宿主显式配置 | 计划中 |
| FIX-07 | `pytest -q tests/test_theme_module.py` | 退订后 `_listeners` 减 1；失效引用被清理；并发 `apply`/`cycle` 不死锁 | 主题热切换观感 | 计划中 |
| FIX-08 | `pytest -q tests/test_error_boundaries.py tests/test_config_framework.py tests/test_telemetry_module.py` | `args` 非空且 4 处 `match=CODE` 全绿；坏 YAML 转 `IOErrorBoundary`；超阈值轮转 | 诊断页事件读取 | 计划中 |
| FIX-09 | `pytest -q tests/test_app_loader.py tests/test_plugin_protocol.py tests/test_page_registry.py` | 重载不抛 `PLUGIN_DUPLICATE_MENU`；无孤儿菜单与模块残留；两文件用例全绿 | 热重载手动触发 | 计划中 |
| FIX-10 | `grep -rn strict_plugins README.md docs src/sllkgui` + `mypy` | 零命中；CHANGELOG 破坏性表有迁移说明 | 下游调用方迁移 | 计划中 |
| FIX-11 | `pytest -q tests/test_language_service.py tests/test_language_coverage.py` | 真实 uic 页面走局部刷新；失败时 `user.yaml` 不变；`main_pages.py` 校验和未变 | 四语言切换后页面状态 | 计划中 |
| FIX-12 | `pytest -q tests/test_page_registry.py tests/test_app_loader.py` | 新断言带自检且能捕获人为重复 ID；`is_default: "false"` 解析为 `False` | 多应用清单冲突提示 | 计划中 |

## 7. 变更追溯

> 回填规则：B1 建立本表；B2–B6 每批回填当批行（commit message 首行 + 变更文件 + 验证结论 + 状态），随本批同一 commit 提交；B7 汇总 7 批短 SHA 全量收口并把结论合入 `CHANGELOG.md` / `ARCHITECTURE.md` / `MANUAL_QA.md`。审阅者可用 `git log --oneline --grep "FIX-"` 与 `git show <sha> --stat` 逐项对照「计划 ID → commit → 变更文件」。

| 编号 | commit | 变更文件 | 验证结果 | 状态 |
| --- | --- | --- | --- | --- |
| FIX-01 | — | — | — | 计划中 |
| FIX-02 | — | — | — | 计划中 |
| FIX-03 | — | — | — | 计划中 |
| FIX-04 | — | — | — | 计划中 |
| FIX-05 | `fix(paths): 移除运行时 cwd 兜底并加固架构守卫自检与规划矩阵 (FIX-05)` | `paths.py` `logger_module.py` `test_no_cwd_runtime_dependency.py` `test_architecture_boundaries.py` `test_legacy_import_policy.py` `docs/CHANGE_PLAN.md` `docs/README.md` `docs/ARCHITECTURE.md` | ruff 0 / mypy 0 / 守卫专项 9 passed / 全量 526 passed, 1 skipped, 覆盖率 72% | 已修复 |
| FIX-06 | — | — | — | 计划中 |
| FIX-07 | — | — | — | 计划中 |
| FIX-08 | — | — | — | 计划中 |
| FIX-09 | — | — | — | 计划中 |
| FIX-10 | — | — | — | 计划中 |
| FIX-11 | — | — | — | 计划中 |
| FIX-12 | — | — | — | 计划中 |
