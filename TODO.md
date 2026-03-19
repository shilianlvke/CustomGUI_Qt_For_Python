# CustomGUI 重构与优化计划

更新日期: 2026-03-19

## 阶段一（低风险高收益）

- [x] 第一步: 重构主窗口按钮分发逻辑（长 if 链 -> 路由分发表 + 专用处理函数）
- [x] 第二步: 替换核心层与入口层的 `import *`，改为显式导入
- [x] 第三步: 依赖治理（区分运行/开发/平台依赖，并补齐 Interface 模块依赖）
- [x] 第四步: 升级日志系统（标准 logging + 文件轮转 + 级别策略）
- [x] 第五步: 建立最小自动化检查（lint + smoke test）

## 阶段二（架构升级）

- [x] 引入配置模型校验（Pydantic 或 dataclass）
- [x] 收敛全局状态（AppContext / ServiceContainer）
- [x] 页面注册机制（页面与菜单解耦）
- [x] 异步任务统一（QThreadPool + 信号总线）
- [x] 分层错误边界（UI/业务/IO）

## 阶段三（产品化）

- [x] 设计令牌化（颜色/字号/间距统一）
- [x] 插件协议（页面、菜单、命令）
- [x] 运行遥测与诊断
- [x] 多平台构建发布流水线
- [x] 文档自动化（架构图/API 文档）

## 第一阶段执行记录

- 2026-03-19: 完成第一步，`main.py` 点击事件由条件分支改为路由分发，新增专用处理函数，后续新增按钮仅需注册路由。
- 2026-03-19: 完成第二步，核心与入口层包导出改为显式导入并补充 `__all__`，降低命名空间污染风险。
- 2026-03-19: 完成第三步，`pyproject.toml` 增加 `windows-hardware` 可选依赖组，`Interface.py` 增加可选依赖缺失时的降级处理，README 同步安装说明。
- 2026-03-19: 完成第四步，`glb_logger.py` 升级为标准 `logging`，增加控制台和文件轮转日志（logs/customgui.log），并从 `console.yml` 读取 `logger_level`。
- 2026-03-19: 完成第五步，新增 `tests/test_smoke.py`、`.github/workflows/ci.yml`，并在 `pyproject.toml` 增加 `dev` 依赖组与基础测试配置。
- 2026-03-19: 为保证自动化检查稳定通过，补充 `tests/conftest.py` 统一仓库根路径导入，并修复 `GUI/windows/loading_window/ui_mian.py` 中 `Loading` 未定义问题。

## 第二阶段执行记录

- 2026-03-19: 阶段二第 1 项完成，新增 `settings_module.py` dataclass 校验器并接入 `folder_tools.py`，对 settings/theme/language 做启动期 fail-fast 校验，同时补充 `tests/test_config_validation.py`。
- 2026-03-19: 阶段二第 2 项完成，`folder_tools.py` 引入 `AppContext` 与懒加载视图，新增 `get_app_context/initialize_app_context`，并在 `main.py` 启动阶段显式初始化上下文。
- 2026-03-19: 阶段二第 3 项完成，新增页面注册表 `PAGE_REGISTRY`，`setup_main_window.py` 与 `main.py` 改为从注册表加载与路由，补充 `tests/test_page_registry.py`。
- 2026-03-19: 阶段二第 4 项完成，`loading_window` 异步执行改为 `QThreadPool + QRunnable(LoadingTask)`，并引入 `LoadingSignalBus` 统一进度/完成/错误信号。
- 2026-03-19: 阶段二第 5 项完成，新增 `error_module.py`（UI/业务/IO 错误边界），并接入 `yaml_handler.py`、`folder_tools.py`、`loading_window/functions.py`，补充 `tests/test_error_boundaries.py`。

## 第三阶段执行记录

- 2026-03-19: 阶段三第 1 项完成，新增 `token_module.py` 统一设计令牌，`GuiCore/styles.py` 与 `left_menu/menu_button.py` 改为 token 驱动，并新增 `tests/test_design_tokens.py`。
- 2026-03-19: 阶段三第 2 项完成，新增 `plugin_module.py` 统一页面/菜单/命令插件协议，页面注册改为插件中心驱动，主窗口增加命令插件分发，补充 `tests/test_plugin_protocol.py`。
- 2026-03-19: 阶段三第 3 项完成，新增 `telemetry_module.py`（本地匿名事件、计时、指标聚合），并接入 `main.py` 与 `loading_window/functions.py`，补充 `tests/test_telemetry_module.py`。
- 2026-03-19: 阶段三第 4 项完成，新增 `scripts/build_package.py` 与 `scripts/archive_dist.py`，并新增 `.github/workflows/release-build.yml`（Windows/Linux 矩阵打包 + tag 发版上传制品）。
- 2026-03-19: 阶段三第 5 项完成，新增 `scripts/generate_docs.py` 自动生成 `docs/ARCHITECTURE.md` 与 `docs/API.md`，并新增 `.github/workflows/docs.yml` 做文档产物上传与同步校验。

## lint 基线治理

- 2026-03-19: lint 基线治理第 1 批完成（`GuiCore/WindowDefineUI/left_menu` 与 `left_column` 核心文件去除 `import *`），全量告警由 728 降至 652（-76），且 `pytest` 26 项通过。
- 2026-03-19: lint 基线治理第 2 批完成（`title_bar`、`grips`、`credits_bar` 去除 `import *` 并补齐 `__all__`），全量告警由 652 降至 560（-92），且 `pytest` 26 项通过。
- 2026-03-19: lint 基线治理第 3 批完成（`GuiCore/CustomUI` 与 `AppDefineUI/dialog` 全量去除 `import *`，并补齐包级 `__all__`），全量告警由 560 降至 462（-98），且 `pytest` 26 项通过。
- 2026-03-19: lint 基线治理第 4 批完成（`AppCore` 导出层与 `GUI/user_define_pages` 去除星号导入并补齐显式导出），全量告警由 462 降至 206（-256），且 `pytest` 26 项通过。
- 2026-03-19: lint 基线治理第 5 批完成（`main_window` 主链路与 `qt_core.py` 去除星号导入并显式依赖化），全量告警由 206 降至 120（-86），其中 `F403/F405` 已清零，`pytest` 26 项通过。
- 2026-03-19: lint 基线治理第 6 批完成（清理剩余 `F401/F541`，包括 UI 生成文件冗余导入与包导出声明统一），全量告警由 120 降至 0，`ruff` 与 `pytest`（26 项）均全通过。
- 2026-03-19: 稳定化收尾完成，`README.md` 新增开发质量门禁与发布前检查清单（`ruff`/`pytest`/文档同步），统一团队提交前自检流程。
