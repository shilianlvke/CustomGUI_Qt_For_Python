# SllkGUI 第三方技术评审报告（3.0.0 整改后复核版）

> 评审对象：`D:/PyPRG/SllkGuiPRG/SllkGui`，分支 `main`，HEAD `d56701f`，版本 `3.0.0`
> 原评审日期：2026-11-19（对象为 `2.7.0` / HEAD `3f36fd7`）
> 本次复核：2026-11-19，逐条核对原报告 `RV-01`..`RV-14` 的整改是否真实落地。
> 方法：读当前代码 + 提交历史 + 本地执行 `pytest` / `ruff` / `mypy` / 定向覆盖率 + AST/grep 实测。
>
> **复核结论**：4 项已彻底关闭（`RV-01`、`RV-06`、`RV-10`、`RV-13`），
> 8 项部分解决、仍有实质残余（`RV-02`、`RV-03`、`RV-04`、`RV-05`、`RV-07`、`RV-08`、`RV-11`、`RV-12`），
> 2 项未解决（`RV-09`、`RV-14`）。因此原文的「全部处理完毕」不准确，本版据实重写。
> 下文第 2 节是仍需处理的事项，第 3 节给出下一步行动；已关闭项只留一行结论与证据索引，不再展开。

---

## 1. 复核实测

环境：Windows 11，Python 3.13（venv）/ 测试解释器 3.12.15，offscreen Qt。

| 命令 | 结果 |
| --- | --- |
| `uv run pytest -q` | 全绿：**704 collected**，703 passed / 1 skipped（`tests/test_fonts.py:34` 的平台条件跳过） |
| `uv run ruff check src tests examples scripts` | `All checks passed!` |
| `uv run mypy` | `Success: no issues found in 17 source files` |
| `uv run pytest --cov=sllkgui --cov-report=term` | TOTAL 30,684 stmts / 7,743 missed / **71%**（阈值 70%） |
| `uv run python -c "import sys,sllkgui.appcore;..."` | `PySide6.QtGui` / `QtCore` 均为 `False`（appcore 已不拉 Qt） |
| `uv run sllkgui plugin lint src/sllkgui/showcase/core_preview` | `ok: true`，0 error / 0 warning |
| AST 统计 `len(guicore.__all__)` / `len(custom_ui.__all__)` | **159 / 105** |

原始评审中「2 条必红用例」「CI 路径含不存在的 `apps`」「import appcore 即拉起 Qt」三项均已消失。
实测不能覆盖的部分：Gitee Go 控制台是否启用门禁（A1）、非 Windows 平台行为（A2）、下游宿主的实际集成方式（A4）——
这些限制沿用原评审假设，本版不改变。

---

## 2. 仍需处理的事项

> 级别沿用原定义：**P1** = 显著抬高改动成本 / 构成一致性风险；**P2** = 工程质量与体验债；
> **P3** = 定位与生态问题，非缺陷。已随整改消解的 P0 不再列出。

### RV-09 · P1（原文 P1，本轮上调为首要）· 失败仍然静默，跨层鸭子类型未收敛 —— 未解决

**现状（两项改进方向均未落地）**：

- `src/sllkgui/guis/windows/main_window/registry.py:79-95`：`ensure_registered_page` 的所有失败分支
  （无路由、上下文缺失、factory 抛错、返回值非 QWidget）仍只写日志 + `report_error`，然后 `return False`；
  最近的等于原报告 `:86-88`，行为未变。
- 错误只进内存：`report_error` 链为 `gallery/context.py:263-272` → `gallery/runtime.py:192-193`
  的 `_report_error`，后者仅 `self.last_error = {...}`（`runtime.py:79`）；全仓无 UI 读取 `last_error`。
  `CToast` 存在于 `guicore/custom_ui/feedback/toast.py:49`，但只用于插件商店与展厅反馈，未接入失败路径。
- `sys.path` 预检抛出的 `PLUGIN_SURFACE_IMPL_MISSING` 在 `gallery/loader.py:228-233` 被捕获后写入
  `registry._errors`；`GalleryRuntime.errors()`（`runtime.py:221-222`）只是转发，**没有 UI/CLI 消费点**。
  于是「插件坏了 → 点了没反应」依然成立，只是触发点从「页面缺失」扩展到所有构建失败。
- 鸭子类型：`src` 下 `getattr(..., None)` 共 **125** 处（原报告 206），集中于
  `guis/windows/main_window/drawers.py`(19)、`controller.py`(18)、`guis/language_service.py`(14)；
  全仓无 `typing.Protocol` 定义（`Protocol` 仅出现在原评审文档的建议里），未收敛到适配器。

**为什么现在优先**：`RV-01` 修好后，失败可见性成为该层唯一的用户可感知缺口；用户仍无法区分「没反应」与「卡住」。

**建议方向**：① 在 `ensure_registered_page` 与加载失败路径统一接入 `CToast` / 页面内错误态，文案含
「插件 ID + 错误码 + 查看日志」入口；② 定义 `MainWindowProtocol` 约束 controller/window 互访，把
`getattr` 收敛到单一适配器。二者无强依赖，可分开提交。

---

### RV-02 · P1 · 门禁仍可「带红通过 / 贴线通过」 —— 部分解决

**已解决**：`pytest` 全绿；`.workflow/QualityGate.yml:62` 的 ruff 路径已去掉不存在的 `apps`；
新增 `ruff format --check`（`:65`）与 `mypy`（`:68`）。

**残余**：

- `.workflow/QualityGate.yml:71`、`.workflow/ReleasePipeline.yml:82` 仍为 `--cov-fail-under=70`；
  实测仍为 **71%**，仅 1 个百分点余量，任何一次小回退都可能穿透。
  文件内注释写「实测约 72%」，比实测乐观 1 个百分点。
- 未输出失败用例清单；未加 `--maxfail=1` 快速门禁。

**建议方向**：阈值改为不低于当前基线（71），随基线上调；CI 失败时输出失败用例清单；
在 PR 模板中要求粘贴 CI 链接。三处改动都只涉及两个 workflow 文件，互不依赖。

---

### RV-03 · P1 · 运行期依赖已闭合，但文档契约仍未回写 —— 部分解决

**已解决**：

- `tests/test_architecture_boundaries.py:27-38` 已是真实的 5×5 白名单矩阵，
  `EDGE_ALLOWLIST` 把 `gallery → guis` 限定在 `gallery/window.py`，`PENDING_INVERSIONS`（`:41`）已清空。
- 运行期边实测：`guicore` 无 `from sllkgui.gallery`；`guis` 对 `gallery` 的引用仅在
  `guis/windows/main_window/registry.py:18-19` 的 `if TYPE_CHECKING:` 块内；`gallery` 对 `guis` 的
  7 处模块级导入全部在白名单允许的 `gallery/window.py:17-30`。环已打破。
- `appcore` 顶层不再拉 Qt（见 §1），`ARCHITECTURE.md:30` 的表述现在成立。

**残余**：`docs/ARCHITECTURE.md:32` 仍写 `gallery` 依赖「appcore + guicore」，未反映组合根对 `guis`
的允许边；`:34` 仍写 `guis.pages` 依赖「guicore + gallery 查询」，与守卫（不允许 `guis → gallery`）
及实际代码矛盾。新契约只写在守卫文件头注释（`:6-13`），未回写架构文档。

**建议方向**：按 `ALLOWED_EDGES` / `EDGE_ALLOWLIST` 改写 `ARCHITECTURE.md` 分层表与依赖说明，
并让文档与守卫的「唯一真相」明确化（可加一条测试比对文档表格，或至少在表下注明以守卫为准）。

---

### RV-04 · P1（原文 P1，本轮下调为 P2）· 插件目录劫持面已消除，脚本残留一处写法 —— 部分解决

**已解决（核心）**：`gallery/loader.py:6-9` 明确不再插入插件目录；`_import_entry()`（`:126-151`）改用
`spec_from_file_location(..., submodule_search_locations=[root])`，误用绝对导入时由 `:42-54` 给出
相对导入提示。`gallery/__init__.py:3-9,55-85` 顶层惰性化（与 `cbc6e7d`/`4c41b45` 一致）。
`_modules_under()`（`:154-174`）仍在且增强了兜底清理，未如建议那样简化——但这是实现选择，非缺陷。

**残余**：`scripts/validate_plugin.py:37` 仍有 `sys.path.insert(0, str(Path(src).resolve() / "src"))`。
该分支在 `sllkgui` 未安装且调用方显式传 `--src` 时执行（`main()` 中 `src = Path(args.src) if args.src else ROOT`）。
风险有限：插入的是**基座自身** `src`，不是插件目录，不构成跨信任边界污染。

**建议方向**：把「不自行修改 sys.path」做实（例如要求安装态运行／用 `python -m`），
或修正 `CHANGELOG.md:81` 「不再自行修改 sys.path」的措辞为「默认不再修改，显式 `--src` 时例外」。

---

### RV-05 · P1 · UI 已归一，配置模型仍是两套 —— 部分解决

**已解决**：`guicore/window/settings/` 与 `guicore/window/left_column/settings_panel.py` 已删除；
`guis/windows/main_window/controller.py` 中 `toggle_settings_drawer` 已无匹配；
`CSettingsWindow.__init__`（`guicore/window/settings_window/window.py:148-154`）注入
`plugin_titles`，guicore 不再 import gallery。

**残余**：

- `appcore/settings/`（7 文件）与 `appcore/sysx/config/`（6 文件）仍并存且都被引用：
  `config.py:83,160,181`、`cli.py:70,359`、`appcore/user_settings.py:45`、`gallery/runtime.py:87`、
  `appcore/settings/store.py:26`。`sysx.config` 并未退化为纯路径工具。
- `appcore/user_settings.py:55` 的 `SUPPORTED_FIELDS` 白名单与 `:104` 的 `_normalize_field` 仍在，
  未换成 schema 校验。新增设置项仍需多处同步。

**建议方向**：先做一次「哪个模型是唯一真相」的决策并落到文档；若确定 `appcore/settings`，
则把 `sysx.config` 的引用逐个迁移、把白名单改为 schema 校验。此项改动面最大，建议放在 S1 之后。

---

### RV-07 · P1（原文 P1，本轮下调 P2）· 兼容壳清空，但 API 面纪律未建立 —— 部分解决

**已解决**：`CPushButton` / `CLineEdit` / `CShowCard` / `CPixmap` 源码与同名文件均已删除；
`register_builtin_menus` / `PAGE_REGISTRY` 已从 `guis/windows/main_window/registry.py` 删除。
原建议的「加弃用警告」随删除而失效，无需再做。
（残留：`guicore/styles_components.py:107-131,173-189` 仍有无对应 `setObjectName` 的死 QSS 选择器。）

**残余**：`guicore.__all__` = **159**、`custom_ui.__all__` = **105**，仍平铺在同一命名空间；
`docs/COMPONENTS.md:3` 仍写「126 / 94」；无「稳定 / 实验 / 弃用」三档的 API 稳定性矩阵。

**建议方向**：顶层 `__all__` 按域拆子命名空间；组件数字改为从 `__all__` 生成（可加一致性测试）；
稳定性矩阵与 `PLUGIN_API_VERSION` 对齐。

---

### RV-08 · P1 · 文档漂移已修复一部分，仍有实质残留 —— 部分解决

**已解决**：`docs/API.md:302-315` §11 已重写为真实符号（`UiMainWindow` / `load_gallery` / `load_run`
等，均在 `window.py.__all__`）；`docs/contributing.md:13` 已去掉 `apps`；
`docs/COMPONENTS.md:71` 已注明兼容壳删除。

**残余**（`grep -rn "apps/" docs/`，排除评审报告自身与明确标注「已删除」的历史说明后）：

| 位置 | 现状 |
| --- | --- |
| `docs/API.md:138` | 优先级仍写「user.yaml > 品牌覆盖层（`apps/<app>/brand`）」 |
| `docs/MANUAL_QA.md:437` | O-01 前置仍为「修改 `apps/<app>/config.yml`」，无历史标注 |
| `docs/MANUAL_QA.md:32` | F-08 指向 `apps/menu_preview/gui/main.py`，虽标注「3.0 已移除」但仍是指令性路径 |
| `docs/icons/README.md:45` | 示例目录仍为 `apps/myapp/` |
| `docs/COMPONENTS.md:3` | 「126 / 94」与实测 159 / 105 不符 |
| `pyproject.toml:18` | 仍为 `Operating System :: OS Independent`，与 Win32 特化分支不符 |

**建议方向**：一次性清理上述 6 处；`COMPONENTS.md` 数字改为生成式；OS classifier 改为真实支持的平台。

---

### RV-11 · P2 · 测试数量上升，覆盖归因与交互断言仍是空白 —— 部分解决

**已解决**：704 用例（原 649）；`tests/test_showcase.py` 7 用例全过，其中 `:91-103`
`test_showcase_pages_direct_build` 直接构建全部 10 个预览页；新增 `tests/test_surface_impl.py`、
`tests/test_data_*.py`（共 19 例）、`tests/test_plugin_store_page.py`（3 例）。

**残余**：

- **全仓覆盖率报告仍把 showcase 各 `page.py` 记为 0%**（如 `data/page.py 80 80 0 0 0%`），
  与「直接 build 测试通过」矛盾。定向实测：单跑
  `pytest tests/test_showcase.py::test_showcase_pages_direct_build --cov=sllkgui.showcase.core_preview.surfaces.data`
  → data 页 **92%**（仅 `build()` 的 219-225 未覆盖）；整文件跑同样的定向 cov 则报
  `CoverageWarning: No data was collected`。说明页面代码确实被执行，问题在**覆盖率归因/动态模块名**，
  而非「没有测试」。根因本轮未定论，不臆测。
- `pyproject.toml:35` 声明 `pytest-qt>=4.4.0`，但全仓 grep `qtbot` / `waitSignal` / `QSignalSpy` 零命中。
- 视觉回归基线未做：`tests/test_component_tokens.py:3-4` 明确写「不比对像素，视觉回归由
  `docs/MANUAL_QA.md` 与展厅负责」。

**建议方向**：先定位并修正覆盖率归因（让全仓报告反映 showcase 实际覆盖）；再二选一——
要么真正使用 `pytest-qt` 做交互断言、要么移除该依赖；视觉基线作为独立决策项。

---

### RV-12 · P2 · 工程化配套大部分补齐，两项与声明不符 —— 部分解决

**已解决**：`.pre-commit-config.yaml`（ruff / ruff-format / mypy / 文本卫生 / `pytest -q -x`）、
`.editorconfig`、`.gitee/ISSUE_TEMPLATE/{bug,feature,plugin}.yml` 与 PR 模板均已就位；
dev 依赖已无 `black`；`scripts/rewrite_imports.py` 已删除。

**残余**：

- **未加 Windows runner**。`QualityGate.yml:73-76` 明写 CI 只有 Linux runner，改为在 Linux 上跑
  `tests/test_cross_platform.py` 做「跨平台降级冒烟」。这是替代方案，不是新增 Windows 流水线；
  Win32 特化分支的真实回归仍无 CI 覆盖。
- `scripts/validate_plugin.py:37` 的 `sys.path.insert` 残留（见 RV-04）。

**建议方向**：明确「只测降级路径」是否是接受的策略；若要真实覆盖，增加 Windows job。
`--src` 分支与 RV-04 一并处理。

---

### RV-14 · P3（定位问题，非缺陷）· 插件信任模型未形成书面边界 —— 未解决

- `docs/PLUGIN.md` 顶部只有原有一句「插件代码运行在 Gallery 进程内……不是沙箱」，无「信任边界声明」专节。
- 信任级别仍是 `official` / `user` 两档（`gallery/source.py:375`、`gallery/state.py:91`），
  UI 仅以 chip 展示（`guis/pages/plugin_store/entries.py:49-51`、`dialogs.py:227-250`），无「官方 / 社区」强制区分。
  `docs/SOURCE.md:97` 声称「自建源安装前会提示『非官方源』」，但代码 grep「非官方」零命中——**文档与代码不符**。
- `EXT-01`（进程隔离）仍只在 `docs/CHANGE_PLAN.md:81` 作为规划。

**建议方向**：在 `PLUGIN.md` 顶部补「信任边界声明」；让 `SOURCE.md:97` 的提示语与代码一致（实现或删句）；
中期按 `EXT-01` 规划进程隔离。

---

## 3. 已关闭事项（不再跟踪，附复核证据）

| 编号 | 结论 | 关键证据 |
| --- | --- | --- |
| **RV-01** data Surface 缺失 | 已解决 | `core_preview/surfaces/data/page.py` 226 行真实实现；`gallery/manifest.py:59-68` 新增 `impl`；`loader.py:177-194` `_verify_surface_impls()` 在加载期校验并抛 `PLUGIN_SURFACE_IMPL_MISSING`（`errors.py:22`），`loader.py:228-233` 捕获入 `registry._errors`；`lint.py:249-264` 提供 `SURFACE_IMPL_UNSPECIFIED`(warn) / `SURFACE_IMPL_NOT_FOUND`(error)；`test_showcase.py` 7 例 + `test_surface_impl.py` 2 例全过。注：error 码名为 `SURFACE_IMPL_NOT_FOUND`，非原报告建议的 `SURFACE_IMPL_MISSING`，功能等价。 |
| **RV-06** 插件商店页 1577 行单文件 | 已解决 | `guis/pages/plugin_store/` 拆为 **7** 个文件（`__init__`/`context`/`theme`/`entries`/`page`/`panels`/`dialogs`）；`_Chip`/`_IconTile`/`_StatTile`/`_ModeCard` 已消失，改用 guicore 的 `CChip`/`CIconTile`/`CMetricCard`/`CSurfacePanel`；有专属测试 `tests/test_plugin_store_page.py`。注：`CHANGELOG.md:93-94` 写「8 个模块」并列出 `widgets.py`，与实际不符（`widgets` 被有意删除并由测试断言不存在），属文档瑕疵，并入 RV-08 处理。 |
| **RV-10** 类型门禁只覆盖 4 文件 | 已解决 | `[tool.mypy]` 已扩到 11 个条目 / **17** 个源文件，`mypy` 通过；承诺边界写入 `pyproject.toml:97-112`、`README.md:886-902`、`docs/ARCHITECTURE.md:51-53`。`py.typed` 与 `Typing :: Typed` 保留——原报告改进方向①允许「移除 classifier **或** README 明示边界」，项目选了后者，符合该方向。 |
| **RV-13** 冻结形态依赖静默失效 | 已解决 | `gallery/dependencies.py:44-50` `is_frozen()`；`:519`/`:637`/`:684-685` 三处抛 `GalleryError(FROZEN_ENV_UNSUPPORTED, ...)`，`errors.py:56` 定义该码；`:53-62` `_frozen_hint()` 给出三种做法，`docs/PLUGIN.md:64-68` / `docs/GALLERY.md:84-86` 同步。 |

---

## 4. 下一步行动

> 优先级与依赖关系基于上述事实；「依赖」列只写真实的前置关系，无前置则写「无」。
> 验收标准均为可执行的检查，不引入新的架构设想。

### 执行顺序

**第 1 批（互不依赖，可并行）**：A1 → A2 → A3 → A4
**第 2 批（在第 1 批稳定后）**：A5 → A6 → A7 → A8
**第 3 批（定位/生态）**：A9

### 第 1 批

| # | 优先级 | 行动 | 涉及文件 / 模块 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- | --- |
| A1 | **P1** | 让 Surface 与加载失败对用户可见（RV-09 ②） | `guis/windows/main_window/registry.py:79-95`、`gallery/runtime.py:79,192-193,221-222`、`gallery/context.py:263-272`；展示用 `guicore/custom_ui/feedback/toast.py` | 无 | 构造一个 factory 抛错的 Surface 并点击入口：UI 出现可见错误提示，含插件 ID、错误码与日志入口；`gallery.registry.errors` 有消费点；新增回归用例断言提示出现 |
| A2 | **P1** | 门禁阈值贴基线 + 失败清单（RV-02） | `.workflow/QualityGate.yml:71`、`.workflow/ReleasePipeline.yml:82`、PR 模板 | 无 | 阈值为 71 或随基线动态上调；人为制造失败时 CI 输出失败用例清单并阻止合并；注释中的「约 72%」与实测一致 |
| A3 | **P1** | 架构文档按守卫矩阵回写（RV-03） | `docs/ARCHITECTURE.md:32,34`（及分层表/关键约定） | 无 | 表中每层的依赖与 `tests/test_architecture_boundaries.py` 的 `ALLOWED_EDGES`/`EDGE_ALLOWLIST` 逐项一致；`gallery→guis` 的组合根例外被写明；守卫测试仍全绿 |
| A4 | **P2** | 处理 `validate_plugin.py` 的 sys.path 残留（RV-04/RV-12） | `scripts/validate_plugin.py:37`、`CHANGELOG.md:81` | 无 | 未安装环境按文档方式调用时不出现 `sys.path.insert`；若保留 `--src` 分支，CHANGELOG 与脚本 docstring 的措辞与之相符 |

### 第 2 批

| # | 优先级 | 行动 | 涉及文件 / 模块 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- | --- |
| A5 | **P1** | 配置模型归一定案并迁移（RV-05） | `appcore/settings/`、`appcore/sysx/config/`、`appcore/user_settings.py:55,104`、`config.py:83,160,181`、`cli.py:70,359`、`gallery/runtime.py:87` | A3（先有统一文档口径）；与 A1 无代码依赖 | 文档明确唯一真相；`sysx.config` 的上述引用按决策迁移或明确保留理由；`SUPPORTED_FIELDS` 改为 schema 校验后，新增设置项只需改一处声明；全量 pytest 全绿 |
| A6 | **P2** | API 面分域与数字生成（RV-07） | `guicore/__init__.py:167-327`、`custom_ui/__init__.py:215-321`、`docs/COMPONENTS.md:3`、`guicore/styles_components.py:107-131,173-189` | A3（文档口径）；与 A5 无依赖 | 顶层只留稳定核心，域子命名空间可用；`COMPONENTS.md` 数字由 `__all__` 生成并有一致性测试；死 QSS 选择器清理或说明 |
| A7 | **P2** | 修正覆盖率归因 + 决定 pytest-qt 去留（RV-11） | `pyproject.toml:35`（pytest-qt）、`tests/test_showcase.py:91-103`、`tests/conftest.py`、coverage 配置 | 无 | 全仓覆盖率报告中 showcase 各 `page.py` 显示非 0 且与定向运行一致（data 页至少覆盖到 `build()` 之外）；`qtbot`/`waitSignal` 有实际用例或依赖被移除 |
| A8 | **P2** | 明确跨平台 CI 策略（RV-12） | `.workflow/QualityGate.yml:73-76`、`tests/test_cross_platform.py`、相关文档 | 无 | 文档与 CI 配置一致：若只测降级路径则明确写出未覆盖范围；若要求真实覆盖则 Windows job 存在且跑 `pytest` |

### 第 3 批

| # | 优先级 | 行动 | 涉及文件 / 模块 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- | --- |
| A9 | **P3** | 书面信任边界与提示语对齐（RV-14） | `docs/PLUGIN.md` 顶部、`docs/SOURCE.md:97`、`gallery/source.py:375`、`gallery/state.py:91`、`guis/pages/plugin_store/entries.py:49-51` | 无 | `PLUGIN.md` 有「信任边界声明」专节；`SOURCE.md:97` 的「非官方源」提示在代码中有实现或该句被删除；信任级别展示与文档一致 |

---

## 5. 值得保留的做法（复核确认仍成立）

1. `gallery/git_backend.py` 的安全约束（URL 白名单、`ext::` 拒绝、空 hooks 目录、`GIT_TERMINAL_PROMPT=0`、全调用超时、不递归子模块）——不要「简化」。
2. `manifest.ensure_within()`：先解析再 `relative_to` 校验，而非字符串前缀。
3. `user_settings._write_atomic()` 的 mkstemp + fsync + os.replace，以及高版本不降级、未知键不丢失。
4. 架构守卫的「扫空即失败」自检（`tests/test_architecture_boundaries.py:52-53`）——防止整类假绿。
5. `src` layout + 测已安装产物（见 `tests/conftest.py:1-6`）——「装完就崩」类问题在合并前暴露。
6. `gallery/loader.py` 的 `spec_from_file_location(..., submodule_search_locations=[root])` 与相对导入提示——替代 `sys.path` 注入的正确做法。
7. 托盘复用 `CPopupMenu`；`examples/plugin-hello` 仍能过 lint（本轮实测 0 error / 0 warning）。

---

## 6. 关键证据索引（复核命令）

| 结论 | 复核命令 |
| --- | --- |
| 全量测试 / ruff / mypy | `uv run pytest -q`；`uv run ruff check src tests examples scripts`；`uv run mypy` |
| 覆盖率与基线 | `uv run pytest --cov=sllkgui --cov-report=term` |
| showcase 归因异常 | `uv run pytest tests/test_showcase.py::test_showcase_pages_direct_build --cov=sllkgui.showcase.core_preview.surfaces.data --cov-report=term-missing -q` 对比 `uv run pytest tests/test_showcase.py --cov=sllkgui.showcase.core_preview.surfaces.data -q` |
| appcore 不拉 Qt | `uv run python -c "import sys,sllkgui.appcore; print('PySide6.QtGui' in sys.modules)"` |
| 公开名数量 | `python -c "import ast,pathlib; ..."`（统计 `__all__` 长度） |
| 分层依赖 | `python -m pytest tests/test_architecture_boundaries.py -q`；读 `ALLOWED_EDGES` |
| 文档漂移 | `grep -rn "apps/" docs/ README.md pyproject.toml` |
| 插件规范校验 | `uv run sllkgui plugin lint examples/plugin-hello` |
| data 从未实现的旧结论已失效 | `git log --oneline -- src/sllkgui/showcase/core_preview/surfaces/data/page.py`（现有文件与提交） |
