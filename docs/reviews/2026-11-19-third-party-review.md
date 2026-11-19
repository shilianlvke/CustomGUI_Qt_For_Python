# SllkGUI 第三方技术评审报告

> 评审对象：`D:/PyPRG/SllkGuiPRG/SllkGui`（分支 `main`，HEAD `3f36fd7`，版本 `2.7.0`）
> 评审日期：2026-11-19
> 评审视角：独立第三方（不参与本项目开发，不做代码修改）
> 方法：目录与提交历史审阅 + AST 依赖矩阵实测 + 本地执行 `ruff` / `mypy` / `pytest` / `sllkgui plugin lint`，逐条对照 `docs/` 中的声明

---

## 0. 结论摘要

**总体判断：这是一个成熟度明显高于"个人开源组件库"平均水平的项目，但正处在"从单人可控到多人可维护"的临界点上，当前的结构债已开始以可见故障的形式外溢。**

三个正面结论先说：

1. **安全与写盘纪律扎实。** Git 后端做了 URL 协议白名单、`ext::` 拒绝、`core.hooksPath` 指向空目录、`GIT_TERMINAL_PROMPT=0`、超时与 `submodule.recurse=false`（`gallery/git_backend.py`）；清单路径用 `ensure_within()` 做解析后包含校验而非字符串前缀；用户配置与插件配置全部 `mkstemp + fsync + os.replace` 原子写，并带显式版本迁移链（`appcore/user_settings.py`）。这套东西通常要踩过事故才会写出来。
2. **"契约单一化"的意识很强。** 插件清单是唯一运行时契约，加载器/安装器/lint/源校验共用 `manifest.py` 一套解析与错误码；架构边界用 AST 扫 import 根守着，并且专门写了"扫空即失败"的自检（`tests/test_architecture_boundaries.py`）来防假绿。
3. **工程化骨架齐全。** src layout + 测试跑已安装包而非源码树、CI 里装了 wheel 再跑 `wheel_smoke.py`、`doctor` 命令、`scaffold` 模板、3,170 行文档 + 592 行人工验收清单。

但同一份代码里也存在**明确的、当下就在发生的**问题：

| 级别 | 结论 |
| --- | --- |
| P0 | `gallery` 模式（项目对外的"组件展厅"门面）有一个必现的功能故障：清单声明了 10 个 Surface，`data` 从未实现，点进去必然报错。main 上 2 个用例长期红色。 |
| P1 | 声明的分层架构与代码实际依赖不一致，且守卫测试存在刚好覆盖不到的盲区（`guicore → gallery`、`gallery ↔ guis` 环、`appcore` 隐式拉 Qt）。 |
| P1 | 插件加载把插件根目录 `sys.path.insert(0, ...)`，等于把每个第三方插件的目录插到标准库之前，构成全进程模块劫持面。 |
| P1 | 设置能力存在三套 UI 与两套配置模型并存，改一个设置项要在 2–3 处同步，且已出现"新增能力只落在其中一套"的迹象。 |
| P2 | 类型门禁只覆盖 4 个文件，却随包分发 `py.typed` 并声明 `Typing :: Typed`，对下游构成事实上的过度承诺。 |

**如果只能做三件事**：修 `data` Surface 并让 CI 真正拦住它（1 天）；把 `sys.path.insert(0)` 换掉（半天）；为"分层"这件事补一个能覆盖 `guicore→gallery` 与 `gallery↔guis` 的判据，再决定是改代码还是改文档（2–3 天）。

**评分（10 分制，第三方横向对标 PySide6 系组件库/桌面基座）：**

| 维度 | 分数 | 一句话依据 |
| --- | --- | --- |
| 结构设计 | 6.5 | 分层意图清晰，但 `guicore`/`gallery`/`guis` 三者互相引用，实际是"网状"而非"分层" |
| 职责边界 | 5.5 | 1,577 行的插件商店页、1,019 行的自绘菜单、三套设置 UI 说明边界靠人自觉而非靠结构 |
| 可扩展性 | 7.0 | 插件协议（清单/Surface/ctx 能力）设计得不错，但插件之间无法互相提供服务 |
| 可维护性 | 5.0 | 54,775 行 / 272 文件，138 处 `except Exception`、206 处 `getattr` 兜底，改动影响面难静态判定 |
| 构建与发布 | 7.5 | uv + hatchling + Gitee Go 双流水线，wheel 冒烟到位；但流水线结论不可信（见 RV-02） |
| 测试 | 6.5 | 649 用例、71% 覆盖、有架构守卫；但 showcase 页面 0% 覆盖且现有红灯无人处理 |
| 配置管理 | 5.5 | 原子写与迁移做得很好，但三套配置模型语义重叠 |
| 文档与协作 | 6.0 | 文档密度罕见，但 7 处引用已删除的 `apps/`，`API.md` 有一整节导出不存在的符号 |

---

## 1. 评审范围、方法与限制

**覆盖范围**

- `src/sllkgui` 全部 5 个子包（272 个 `.py`，54,775 行）
- `tests/`（66 个文件，收集到 649 条用例）
- `docs/`（15 篇，3,170 行）、`README.md`（36.9 KB）、`CHANGELOG.md`
- `.workflow/`（QualityGate / ReleasePipeline）、`scripts/`、`examples/`、`pyproject.toml`

**实测命令与结果**

| 命令 | 结果 |
| --- | --- |
| `uv run ruff check src tests examples scripts` | `All checks passed!`（0 告警） |
| `uv run mypy` | `Success: no issues found in 4 source files` |
| `uv run pytest -q` | **2 failed**（均在 `tests/test_showcase.py`），其余通过 |
| `uv run pytest --cov=sllkgui` | TOTAL 32,007 stmts / 8,037 missed / **71%** |
| `uv run sllkgui plugin lint examples/plugin-hello` | `ok: true`，0 error 0 warning |
| AST 依赖矩阵扫描 | 见 §2.1 |

**假设（信息不足处，按此理解）**

| 编号 | 假设 | 若不成立的影响 |
| --- | --- | --- |
| A1 | 无法访问 Gitee Go 控制台，无法确认 `QualityGate` 是否启用、最近一次运行是否为红。据此推断"门禁未对 main 生效" | 若流水线确实在跑且为红，则问题性质从"门禁缺失"变为"红灯被忽略"，更严重 |
| A2 | 仅在 Windows 11 + Python 3.13 venv 下实测；Linux/macOS 行为按代码推断 | 平台相关结论（亚克力、`ctypes`、字体）可能有偏差 |
| A3 | 未审阅完整 git 历史（仅近 15 条提交 + 关键文件定向追溯） | 某些"兼容层"可能是刚引入而非遗留，判断会偏保守 |
| A4 | 未获取下游宿主（`py-cl2` 等）的实际集成方式与 `ctx.*` 真实使用频次 | 插件 API 的"过宽"判断可能高估 |
| A5 | 性能结论引用代码注释中的实测数字，未独立复测 | 若注释过时，性能判断失效 |

**明确未覆盖的盲区**：i18n 四语言翻译质量、649 条用例的断言强度（仅抽样）、内存/句柄泄漏、渗透测试、`paintEvent` 渲染性能实测、PyInstaller 产物实机运行。

---

## 2. 系统结构诊断

### 2.1 分层：文档写的是"塔"，代码实际是"网"

`docs/ARCHITECTURE.md` 声明的依赖关系是：

```
appcore（标准库）  →  guicore（PySide6）  →  gallery（appcore + guicore）  →  guis  →  showcase
```

AST 实测（模块级导入 = 导入期即生效；延迟导入 = 运行期生效）：

| 源 → 目标 | 模块级 | 函数内延迟 | 文档是否允许 |
| --- | ---: | ---: | --- |
| `guicore → appcore` | 86 | 6 | ✅ 允许（但 86 处意味着强耦合） |
| `gallery → appcore` | 13 | 4 | ✅ 允许 |
| `gallery → guicore` | 1 | 8 | ✅ 允许 |
| **`gallery → guis`** | **7** | 0 | ❌ **文档写的是"appcore + guicore"** |
| **`guis → gallery`** | **1** | 3 | ❌ 未声明，与上一行构成环 |
| **`guicore → gallery`** | 0 | **3** | ❌ **底层依赖上层，且现有守卫测不到** |
| `guis → guicore` | 15 | 0 | ✅ 允许 |
| `showcase → guicore` | 9 | 0 | ✅ 允许 |
| `showcase → guis` | 0 | 2 | ⚠️ 未声明 |

**判断依据（可复核）**

- `gallery/window.py` 模块级导入 `guis.windows.main_window.*` 共 7 项 —— `GalleryWindow` 是外壳，作为组合根依赖 `guis` 尚可辩护，但它同时被 `guis` 反向依赖，环就成立了。
- `guis/windows/main_window/registry.py` 模块级导入 `sllkgui.gallery.registry`（`current_registry` / `GalleryRegistry`）。
- `guicore` 反向依赖出现在 3 处，全部在设置界面里、且全部写在函数体内（延迟导入正是为了绕开导入期循环）：
  - `guicore/window/settings/sections.py:573`
  - `guicore/window/settings_window/window.py:501`
  - `guicore/window/left_column/settings_panel.py:302`
  —— 三处都只为了拿"插件显示名"（`current_registry().plugins()`）。

**守卫测试为什么没拦住**

`tests/test_architecture_boundaries.py` 检查了三条规则：`appcore ⊁ guis/guicore`、`guicore ⊁ guis`、`guis/guicore ⊁ appcore.sysx`。它**没有**检查 `guicore → gallery`，也没有检查 `gallery → guis`。也就是说：规则集是按"当时的历史债"逐条加的，而不是按"分层是否闭合"推导出来的；一旦出现新的反向边，测试依旧全绿。

**影响范围**

- 组件库无法被单独复用（这是一个"UI 基座"最核心的卖点）：任何想只用 `guicore` 的下游，都会因为 `sections.py` 里那三行 `from sllkgui.gallery.registry import ...` 而被迫接受整个插件系统。
- 重构影响面无法静态推导：`guicore` 里任何改动都可能通过延迟导入在运行期才炸，且只在打开设置窗口时炸。
- `appcore` 的"纯标准库"定位名不副实（见 §2.4）。

**风险等级**：P1（不会立刻故障，但会持续放大每一次改动的成本；且随代码增长单调恶化）

**改进方向（二选一，必须选一个并落到文档）**

- **方案 A（推荐，改代码）**：把"插件显示名"这类信息抽象成 `guicore` 能接受的**数据注入**——设置窗口构造时接收 `plugin_titles: dict[str, str]`，由 `guis` 装配层填充。这样 `guicore` 不再认识 `gallery`，反向边消失。
- **方案 B（改文档 + 加守卫）**：承认 `guicore`/`gallery` 属于同一"平台层"，把 `ARCHITECTURE.md` 的分层表改成"平台层（`guicore` + `gallery`）"，并把守卫扩展到"禁止 `appcore` 依赖平台层"，同时显式允许 `platform ↔ gallery`。代价是放弃"组件库可独立复用"的叙事。

无论选哪个，守卫测试都应改成**白名单式**：显式列出允许的 5×5 边，出现新边即失败。这比"逐条禁止"更接近真实意图，也不会因为新增合法依赖而误伤。

### 2.2 `appcore` 并非"纯标准库"——实测导入即拉起 Qt

```
$ uv run python -c "import sys, sllkgui.appcore; print('PySide6.QtGui' in sys.modules)"
True
```

根因：`appcore/__init__.py` 导出 `PathFactory` / `PicFixFactory` → `appcore/sysx/__init__.py` → `appcore/sysx/common/static_func.py`，该文件模块级 `from PySide6.QtCore import QRectF, Qt` / `from PySide6.QtGui import QPainter, QPainterPath, QPixmap`。

**影响**：(a) `ARCHITECTURE.md` 的依赖表与事实不符；(b) `scripts/validate_plugin.py` 声称"不需要启动 Qt"，实际仍要求安装 PySide6（约 200 MB）才能对插件做规范校验，与"供源仓库 CI 使用"的定位有摩擦；(c) `CHANGE_PLAN.md` 的 `EXT-12`（appcore 去 Qt）不是"未来项"，而是**已经被破坏的现状**。

**优先级** P2；**修复**：`PathFactory` 的 SVG/绘制能力下沉到 `guicore`，`appcore` 只保留路径解析（`find_resource`/`resolve_path`）；或拆出 `appcore.paths` 独立子包供 CLI 使用。

### 2.3 职责边界：三个"超载点"

| 模块 | 规模 | 实际承担的职责 | 问题 |
| --- | --- | --- | --- |
| `guis/pages/plugin_store.py` | 1,577 行 / 50+ 类 | 页面骨架 + 卡片/徽章/图标块/统计块/模式卡的**自绘控件实现** + 安装/卸载/更新**业务编排** + 详情对话框 + 面板容器 + 主题取色 | 一个文件横跨"控件层/业务层/页面层"；其中 `_Chip`/`_IconTile`/`_StatTile`/`_ModeCard`/`_ElidedLabel` 是对 `guicore` 已有组件（`CChip`/`CTag`/`CProgressBar`…）的重复实现 |
| `guicore/custom_ui/menu/` | 12 模块 / 4,168 行 | `CMenu`(QMenu 子类)、`CMenuList`(自绘列表)、`CPopupMenu`(自绘弹出，1,019 行) **三代并存**；另有 `CMenubar`/`CTieredMenu`/`CMegaMenu`/`CPanelMenu`/`CContextMenu`/`CTabMenu` | 插件作者面对 10 个菜单类，`docs/COMPONENTS.md` 只并列罗列，没有"什么时候用哪个"的决策树；`CTieredMenu`(24 行) / `CPanelMenu`(38 行) 已是薄壳 |
| `guis/windows/main_window/controller.py` | 756 行 / 4 类 | 窗口状态持久化 + 路由 + 设置抽屉 + 设置窗口 + 主题预览 + 背景图 + 菜单模式 + 抽屉模式 + 快捷键同步 | `SettingsController` 与 `MainWindowController` 职责重叠（两者都有 `toggle_settings_drawer` / `open_settings_window` / `open_settings_page`），调用链需靠 `getattr` 探测 |

**判断依据**

- `plugin_store.py` 自身已 `from sllkgui.guicore import CButton, CDataView, CToggleSwitch, ...`，说明作者知道该用组件库，但仍在同文件内重造了 5 个视觉件 —— 这通常意味着"组件库缺这个能力"或"这个页面不想受组件库约束"，两种情况都需要显式决策，而不是默认重造。
- 菜单三代并存的直接证据：`gallery/tray.py:544` 用 `CPopupMenu`（新）；`docs/COMPONENTS.md:99` 主推 `CMenu`（旧，QMenu 子类）；`CMenuList` 与 `CPopupMenu` 都实现了"多面板/滚动/贴边"，功能重叠。

**影响**：主题与设计令牌调整时，自绘控件的取色路径与组件库不同（`plugin_store.py` 直接 `from sllkgui.guicore.styles import card_surface_color`），容易在一次主题重构后出现"这一页没跟着变"。

**改进方向**

1. `plugin_store.py` 按"控件 / 业务 / 页面"三段拆为 `pages/plugin_store/{widgets,actions,page}.py`；`widgets` 里的 5 个自绘件先判"能否用现有组件 + 参数化"，不能的**上移到 `guicore`** 而不是留在页面里。
2. 菜单收敛：明确"新代码只用 `CPopupMenu`"，`CMenu`/`CTieredMenu`/`CPanelMenu` 标注 `@deprecated` 并在 `docs/COMPONENTS.md` 加决策表；`CMenuList` 若只是 `CPopupMenu` 的内核，合并进 `popup_menu.py` 的私有实现。
3. `SettingsController` 与 `MainWindowController` 合并为一个，或明确分工：前者只管"设置窗口/预览/保存"，后者只管"窗口装配与路由"，并删掉重复的转发方法。

### 2.4 可扩展性：插件协议的能力矩阵

**做得好的部分**：清单驱动、`plugin_id/surface_id` 路由派生页面 objectName、`ctx` 能力按域切分（`settings`/`tray`/`shortcuts`/`language`/`log`/`event`/`timing`）、托盘与快捷键由基座持唯一实例避免插件争抢、权限声明用于知情同意。这是一套设计过的协议，不是随手拼的。

**能力缺口（按对生态的影响排序）**

| 缺口 | 现状 | 后果 |
| --- | --- | --- |
| 插件之间无法互供服务 | 只有 `dependencies`（加载顺序/版本约束）+ 页面跳转 `ctx.open_surface` | 想做"插件 A 提供数据、插件 B 展示"必须各自读文件或重复实现 |
| 无插件级事件总线 | `record_event` 是单向遥测，无订阅 | 插件无法响应"语言切换完成""主题已应用""插件 X 已加载" |
| 无导航钩子 | `open_surface` 只能发起，无法拦截/装饰 | 无法实现"未保存时拦截离开""面包屑由插件贡献" |
| 无契约化存储 | 插件自己建文件（lint 只禁日志 handler） | 卸载不清理、备份不完整、跨插件冲突 |
| Surface 无生命周期 | 惰性构建后常驻，只有 `on_load`/`on_unload` | 重页面无法在离开时释放资源 |

**这些不是缺陷，是"还没到那一步"**。但 `docs/PLUGIN.md` 目前把协议描述成完备的，建议加一节"当前不支持的能力"，避免插件作者按想象中的 API 设计架构后返工。

### 2.5 可维护性：可量化指标

| 指标 | 实测值 | 解读 |
| --- | ---: | --- |
| `except Exception` | 138 | GUI 框架里失败隔离是必要的，但 138 处意味着"异常路径"基本没有统一策略；配合 58 处 `# noqa: BLE001` 说明作者清楚这是债 |
| `getattr(obj, "attr", None)` | 206 | 跨层访问靠鸭子类型，重构无静态保护；典型如 `getattr(getattr(window, "ui", None), "settings_drawer", None)` 连续三层 |
| `# noqa` 总数 | 535 | 其中 467 条是 `N802`（Qt 方法命名），属正当豁免；剩余 68 条中 `BLE001` 占 58，集中在加载器/设置/托盘 |
| `global` 语句 | 19 | 全局单例（`_CURRENT_RUNTIME`、`_CACHE`、`_PROVIDER_REGISTERED`…），测试隔离靠 `reset_*()` 手工复位 |
| 最大文件 | 1,577 行 | 超过 800 行的文件有 6 个，均在 `guicore`/`guis`/`gallery` 的核心路径上 |
| 组件库公开导出 | 160（`guicore.__all__`） | `docs/COMPONENTS.md` 写"126 个公开名"，实际 `custom_ui` 也已是 105（文档写 94） |

---

## 3. 问题清单

> 级别定义：**P0** = 当前版本用户可见的功能故障或数据风险；**P1** = 显著抬高后续改动成本、或构成安全/一致性风险；**P2** = 工程质量与体验债。

### RV-01 · P0 · 内置预览插件声明了不存在的 Surface，`gallery` 模式必现失败

- **位置**：`src/sllkgui/showcase/core_preview/sllkgui-plugin.yml`（声明 `data`）/ `src/sllkgui/showcase/core_preview/surfaces/`（无 `data` 目录）
- **触发条件**：`sllkgui gallery` → 点击左菜单「数据展示」
- **错误行为**：`SURFACE_BUILD_FAILED: No module named 'sllkgui_plugin_....surfaces.data'`；页面不出现，仅写日志
- **实际影响**：这是项目对外的**组件展厅**（`docs/GALLERY.md` 定位），10 个入口里 1 个是坏的；同时 `tests/test_showcase.py` 的 2 条用例长期红，等于门禁的"红"已经常态化
- **证据**：`pytest tests/test_showcase.py` 输出；`git log --all -- .../surfaces/data` 为空（该目录**从未存在**）；`git log -S"id: data"` 指向 2.0 迁移提交 `dffec93`
- **根因**：清单声明与实现之间没有校验点。加载器只在"点击时"构建 Surface（`registry.ensure_registered_page`），`lint` 只检查图标存在，不检查 `surfaces/<id>/page.py` 是否存在
- **改进方向**：① 补齐 `data` 页或从清单删除（产品决策，1 小时内可完成）；② `load_plugin` 成功后对每个 Surface 做**存在性预检**，失败在启动期进入 `registry.errors` 而非点击期；③ `lint` 增加 `SURFACE_IMPL_MISSING`（error 级）

### RV-02 · P1 · 质量门禁的可信度不足

- **位置**：`.workflow/QualityGate.yml`、`tests/test_showcase.py`
- **判断依据**：门禁声明"向 main 提 PR 或推送 main 即跑 ruff + mypy + pytest + 覆盖率 70%"。而当前 `main` 上 `pytest` 有 2 条必然失败（纯逻辑错误，与平台无关），说明**门禁从未拦住这批改动**。覆盖率 71% 距阈值 70% 仅 1 个百分点，任何一次小改动都可能穿透
- **影响**：门禁从"质量信号"退化为"装饰物"；贡献者看到红也无人处理，会迅速形成"红是正常的"文化
- **风险**：若门禁实际在跑且长期红（假设 A1 的另一支），则说明流程纪律已经失效，比"没启用"更难纠正
- **改进方向**：① 先让 `pytest` 全绿并合并；② 覆盖率阈值改为"不低于当前值"（71→ 随代码上调，而不是固定 70）；③ 在 CI 里加"失败用例清单"输出，PR 模板要求贴 CI 链接；④ 加 `pytest -q --maxfail=1` 的快速门禁，先保证"有红必拦"

### RV-03 · P1 · 分层契约与代码不符，守卫测试存在结构性盲区

详见 §2.1。**位置**：`guicore/window/settings/sections.py:573`、`guicore/window/settings_window/window.py:501`、`guicore/window/left_column/settings_panel.py:302`、`gallery/window.py`、`guis/windows/main_window/registry.py`、`tests/test_architecture_boundaries.py`
**改进方向**：见 §2.1 的方案 A/B；守卫改为 5×5 白名单矩阵。

### RV-04 · P1 · 插件加载把插件目录插到 `sys.path[0]`，构成全进程模块劫持面

- **位置**：`src/sllkgui/gallery/loader.py:44` — `sys.path.insert(0, text)`
- **触发条件**：任何插件仓库根目录下存在与标准库/三方库同名的模块（`json.py`、`typing.py`、`yaml.py`、`requests.py`…）
- **错误行为**：该模块在**整个宿主进程**内优先于标准库被导入，影响后续加载的所有插件与基座自身
- **证据**：代码路径明确（`_add_sys_path` 无任何同名冲突检查）；`lint` 明文禁止插件修改 `sys.path`，但基座自己做了这件事
- **影响**：从"插件行为异常、难以定位"到"恶意插件劫持宿主依赖"；也解释了为什么卸载逻辑要写 `_modules_under()` 遍历全部 `sys.modules` 按文件路径清理 —— 这是为 `sys.path` 方案付出的复杂度代价
- **风险评估**：不是"已被利用的漏洞"，但它是**唯一一处基座主动引入的、跨信任边界的污染**
- **改进方向**：① 改为 `sys.path.append()` 并检测冲突（同名模块已存在则拒绝加载并给出错误码）；② 更好的做法是彻底去掉——`spec_from_file_location(..., submodule_search_locations=[root])` 已经让入口模块成为包，插件内部用相对导入即可；确有绝对导入需求时，用 `importlib` 自定义 Finder 只在 `module_name` 前缀下解析；③ 无论哪种，卸载逻辑可以据此大幅简化

### RV-05 · P1 · 三套设置 UI + 两套配置模型并存

| 实现 | 位置 | 状态 |
| --- | --- | --- |
| `CSettingsDrawer`（抽屉） | `guicore/window/settings/`（`sections.py` 1,083 行 + `drawer.py` 452 行） | 仍在用：`MainWindowController._ensure_settings_drawer` / `toggle_settings_drawer` |
| `CSettingsWindow`（独立窗口，schema 驱动） | `guicore/window/settings_window/`（900 + 769 行） | 新主推：`base.settings` 快捷键优先走它 |
| `CSettingsPanel`（左栏内嵌） | `guicore/window/left_column/settings_panel.py` | **只被一个测试引用**（`tests/test_shell_components.py:223`），疑似死代码 |

配置模型同样是两套：`appcore/sysx/config/`（dataclass + YAML 强类型，`schema.py` 765 行）与 `appcore/settings/`（声明式 `Setting`/`SettingSpec` + registry + store + session，`schema.py` 768 行），外加 `appcore/user_settings.py` 的 `SUPPORTED_FIELDS` 白名单，三个地方描述同一批配置键（`theme_name` ↔ `core.appearance.theme`）。

- **证据**：`pyproject.toml` 的覆盖率配置显示 `guicore/window/settings/*` 与 `settings_window/*` 同时被测；`docs/SETTINGS.md` 描述的是新框架，但 `docs/API.md:141` 仍以"user.yaml > 品牌覆盖层"描述旧优先级
- **影响**：新增一个设置项需要改动：`Setting` 声明 → `SchemaPage._build_control` 分支 → `user_settings._normalize_field` 白名单 → 旧抽屉的 `sections.py` 对应 section（若还要兼容）。任一处遗漏即"设置不生效"，而这类 bug 最难在测试里发现
- **改进方向**：**把 `appcore/settings` 定为唯一真相**；`user_settings.py` 退化为 `CoreSettingsBackend` 的存储实现（已被 `store.py` 包装，只差把白名单换成 schema 校验）；`CSettingsDrawer` 若产品上仍需要"快捷抽屉"，改为复用 `SchemaPage` 的子集渲染（同一份 schema，两种壳），不再维护第二套 section 代码；`CSettingsPanel` 若无产品用途直接删

### RV-06 · P1 · 插件商店页是"自成一体的 UI 子系统"

见 §2.3 第一行。**补充影响**：该页是"插件生态"的入口，却最不受组件库约束，意味着组件库的任何视觉升级都无法自动覆盖它；且 1,577 行没有专属测试文件，仅在 `test_showcase.py` 里以 3 条用例覆盖页面注册与重载路径（视觉与业务分支未被断言）。

### RV-07 · P1 · 公开 API 面无版本纪律

- **证据**：`guicore.__all__` 160 项、`custom_ui.__all__` 105 项，全部平铺在同一个命名空间；含未标记弃用的兼容壳 `CPushButton`（`push_btn.py` 首行自述"旧版通用按钮"）、`CLineEdit`（`line_edit.py` 首行自述"旧版单行输入框"）；`guis/windows/main_window/registry.py` 保留空函数 `register_builtin_menus()` 与 `PAGE_REGISTRY: list = []`
- **矛盾**：`docs/ARCHITECTURE.md:44` 明确写"旧 App 协议已删除，**不保留兼容层**"，但代码里兼容层仍在，且在一级导出
- **影响**：下游无法判断"哪些名字可以用到 3.0"；一旦有人在生产里用了 `CPushButton`，未来删除就是破坏性变更
- **改进方向**：① 兼容壳加 `DeprecationWarning` 并在 `docs/COMPONENTS.md` 标注 `@deprecated since 2.x, removed in 3.0`；② `guicore.__all__` 按域拆子命名空间（`guicore.widgets` / `guicore.window` / `guicore.menu`），顶层只留稳定核心；③ 与 `PLUGIN_API_VERSION` 对齐，发布 `API 稳定性矩阵`（稳定/实验/弃用三档）

### RV-08 · P1 · 文档与代码漂移，且已漂到"照着做会报错"的程度

| 位置 | 声明 | 实际 |
| --- | --- | --- |
| `docs/API.md:302-316` | `from sllkgui.window import AppContext, AppHandle, discover_app_dirs, load_apps, ...` | 这些符号**不存在**（App 协议已删除） |
| `docs/API.md:141` | "优先级：user.yaml > 品牌覆盖层（`apps/<app>/brand`）> 基座默认" | `apps/` 已删除 |
| `docs/COMPONENTS.md:3` | "共导出 126 个公开名，`custom_ui` 94 个" | 实测 160 / 105 |
| `docs/COMPONENTS.md:288` | "`apps/` 下的 10 个示例应用就是组件目录的活文档" | 现为 `showcase` 的 9 个 Surface（第 10 个还是坏的） |
| `docs/contributing.md:13` | `uv run ruff check src tests apps examples scripts` | `apps/` 不存在 |
| `docs/MANUAL_QA.md` 多处 | 指向 `apps/menu_preview/gui/main.py` 等 | 路径不存在 |
| `pyproject.toml:18` | `Operating System :: OS Independent` | `acrylic.py`/`shortcuts.py`/`gallery/window.py` 有 Win32 `ctypes`/`winreg` 分支 |

- **影响**：新贡献者按 `contributing.md` 跑第一条命令就遇到路径错误；插件作者按 `API.md` §11 写导入直接 `ImportError`。文档密度是本项目的优势，但**过时的高质量文档比没有文档更伤信任**
- **改进方向**：① 一次性清理 7 处 `apps/` 引用；② 删除或重写 `API.md` §11；③ 把 `COMPONENTS.md` 的数字改为"从 `__all__` 生成"，避免手写漂移（可加一条测试：`len(guicore.__all__)` 与文档表格一致）；④ `contributing.md` 的命令与 `.workflow` 保持单一来源

### RV-09 · P1 · 跨层鸭子类型 + 失败静默

- **证据**：206 处 `getattr`；`ensure_registered_page` 在 Surface 构建失败时 `return False`，只写日志与 `report_error`，UI 层无任何提示（`guis/windows/main_window/registry.py:86-88`）—— RV-01 的用户体验正是被这一点放大的：点了没反应
- **影响**：① 重构靠"跑一遍看看有没有 AttributeError"；② 用户遇到坏插件时无法区分"没反应"和"卡住了"
- **改进方向**：① 定义 `MainWindowProtocol`（`typing.Protocol`）约束 controller 与 window 的互访，把 `getattr` 收敛到一处适配器；② `ensure_registered_page` 失败时通过 `CToast` 或页面内 ErrorBoundary 展示，并给出"插件 ID + 错误码 + 查看日志"的入口

### RV-10 · P2 · 类型门禁只覆盖 4 个文件，却对外承诺"Typed"

- **位置**：`pyproject.toml` `[tool.mypy] files = [config.py, callbacks.py, task.py, user_settings.py]`；`src/sllkgui/py.typed` 存在；classifier 含 `Typing :: Typed`
- **数据**：4 个文件约 1.3k 行 / 全部 54,775 行 ≈ **2.4%**
- **影响**：下游（尤其 `py-cl2` 这类真实宿主）会因 `py.typed` 认为可以依赖类型信息，实际拿到的是 `Any`（`follow_imports = "skip"`），IDE 补全与类型检查都会失真
- **权衡说明**：`pyproject.toml` 的注释已经解释了"增量门禁"的合理性 —— 这个决策本身是对的，问题只在于**对外承诺与内部策略不匹配**
- **改进方向**：① 保留增量门禁，但移除 `Typing :: Typed` classifier，或在 `README` 明示"类型检查覆盖公共 API 子集"；② 每季度把 `files` 扩 2 个模块（优先 `gallery/*`，它是插件契约面）；③ 对 `sllkgui.plugin` 的导出加 `py.typed` 级的严格检查

### RV-11 · P2 · 测试结构：数量够，分布与断言强度不均

- **数据**：649 用例 / 66 文件 / 71% 行覆盖；`showcase/**/page.py` 全部 0%（9 个文件、1,667 行）——因为唯一会构建它们的测试是红的
- **结构观察**：`gallery` 有 14 个测试文件（质量最好的一层，含 `test_gallery_manifest` / `resolver` / `git` / `store` / `dependencies`，边界与错误码覆盖到位）；`guicore` 组件测试多为"构造成功 + 属性断言"，缺少"主题切换后颜色跟随""键盘可达性""高 DPI 缩放"这类行为断言；无视觉回归基线（`docs/MANUAL_QA.md` 592 行正是这块缺口的补偿）
- **改进方向**：① 修好 RV-01 后 `showcase` 立刻有覆盖，其 9 个 Surface 可作为"组件库集成冒烟"；② 引入 `pytest-qt` 的 `qtbot.waitSignal` 做交互断言，替代 `getattr` 探测；③ 视觉回归可用离屏 `grab()` 截图 + 感知哈希基线（成本低、无需真机）

### RV-12 · P2 · 工程化配套缺口

| 缺口 | 现状 | 建议 |
| --- | --- | --- |
| 无 `pre-commit` | 依赖人记得跑三条命令 | 加 `.pre-commit-config.yaml`（ruff + ruff-format + 本地 `pytest -q -x`） |
| 无 `.editorconfig` | 换行/编码/缩进靠口头约定 | 加，尤其本项目有 `.ui`/`.yml`/`.py` 混合 |
| 格式化工具未定 | `black` 在 dev 依赖里但**无配置、无门禁、CI 不跑** | 二选一：删 `black`，或改用 `ruff format`（与现有 ruff 同源，零额外成本） |
| 单平台 CI | 仅在 Gitee Go Linux 跑；代码含 Win32 特化分支 | 至少加 Windows runner 跑 `pytest`（亚克力/托盘/快捷键的回归只可能在 Windows 暴露） |
| 无 issue/PR 模板 | 缺陷报告缺少"版本/模式/插件 ID/日志"结构 | 加 `.gitee/ISSUE_TEMPLATE`，与 `doctor` 输出对齐 |
| `scripts/rewrite_imports.py` | 一次性迁移脚本长期驻留，无测试 | 归档到 `scripts/legacy/` 或删除 |
| `scripts/validate_plugin.py` | 内部 `sys.path.insert(0, ROOT/"src")`（正是 lint 禁止插件做的事） | 改用 `python -m` 或安装态调用 |

### RV-13 · P2 · 冻结形态与"插件自动装依赖"能力不匹配

- **位置**：`gallery/dependencies.py:108`（`[sys.executable, "-m", "pip", "--version"]`）、`:596`（`uv pip install --python sys.executable`）
- **触发条件**：宿主以 PyInstaller 冻结形态分发（`scripts/build_package.py` 正是这么做的），或下游把自己的应用冻结
- **错误行为**：`sys.executable` 指向冻结 exe，`-m pip` 必然失败；`uv pip install --python <exe>` 同样失败。代码中**无** `getattr(sys, "frozen", False)` 分支，失败会退化为"依赖未就绪，已跳过"，并给用户一条同样跑不通的手动命令
- **影响**：插件生态的核心卖点（声明 `python_dependencies` 自动就绪）在冻结分发下静默失效
- **说明**：主分发路径（启动器 bootstrap 出真实 venv）不受影响，因此定为 P2；但 `ReleasePipeline` 产出的 PyInstaller 包是官方产物之一
- **改进方向**：检测 `sys.frozen`/`sys._MEIPASS`，给出明确错误码 `FROZEN_ENV_UNSUPPORTED` 与文档说明；或在冻结产物里改走"随包 vendored 依赖"策略（`resolver.py` 的 docstring 已提到 `vendor/` 自包含，只是 `dependencies.py` 未实现）

### RV-14 · P2 · 插件信任模型的上限（定位问题，非缺陷）

- **现状**：插件在宿主进程内 `exec_module`；权限是**知情同意**（文档已明示"不是沙箱"）；`verify` 只能证明"安装后未被本地篡改"（manifest SHA-256 + Git HEAD + 工作区干净），无法证明"作者可信"——因为哈希来自安装记录本身
- **影响**：这决定了项目能走多远。作为"内部/可信来源的基座"完全够用；若要做公开插件市场，`RV-04`（`sys.path` 劫持）+ 无签名 + 同进程，三者叠加意味着**任何插件等价于宿主权限**
- **建议**：短期不投入沙箱（成本极高、收益依赖生态规模），但应在 `docs/PLUGIN.md` 顶部加一节"信任边界声明"，并给源仓库加"官方/社区"信任级别的**强制**区分（现在 `DEFAULT_SOURCE_TRUST` 有字段，但 UI 是否强提示需确认）。中期按 `EXT-01` 走独立进程 + 受限 IPC

---

## 4. 值得保留的做法（避免后续重构误伤）

1. **`git_backend.py` 的安全约束**：URL 白名单、`ext::` 拒绝、空 hooks 目录、`GIT_TERMINAL_PROMPT=0`、全调用超时、不递归子模块。这套组合是对的，重构时不要"简化"。
2. **`manifest.ensure_within()`**：先解析再 `relative_to` 校验，而不是 `str.startswith` —— 正确的路径包含判定。
3. **原子写 + fsync + `mkstemp`**（`user_settings._write_atomic`）：包括"高版本文件不降级、未知键不丢失"的处理，是踩过坑才会写的代码。
4. **架构守卫的"扫空即失败"自检**：`_iter_python_files` 里 `assert found` —— 这条断言防止了整类"假绿"。
5. **`src` layout + 测已安装包**：`conftest.py` 明确不往 `sys.path` 塞源码目录，`wheel_smoke.py` 在 CI 里装 whl 再跑。这让"装完就崩"类问题在合并前暴露。
6. **托盘复用 `CPopupMenu`** 而非自建菜单（`tray.py:544`）—— 新代码在正确的地方复用。
7. **`examples/plugin-hello` 能过 lint**（实测 0 error / 0 warning）—— 示例与规范一致，插件作者的第一次体验是通的。

---

## 5. 演进路线

### S1 · 止血（1–2 周）

| 目标 | 优先级 | 依赖 | 预期收益 |
| --- | --- | --- | --- |
| 修复或移除 `data` Surface，`pytest` 全绿 | P0 | 无 | 对外门面恢复可用；门禁重新有信号 |
| Surface 实现存在性预检 + lint `SURFACE_IMPL_MISSING` | P0 | 上一条 | 同类问题不再靠用户点击发现 |
| `sys.path.insert(0)` → `append` + 冲突拒绝（或改自定义 Finder） | P1 | 无 | 消除跨插件模块劫持面；简化卸载逻辑 |
| 文档漂移一次性清理（`apps/` 7 处、`API.md` §11、`COMPONENTS.md` 数字、`contributing` 命令） | P1 | 无 | 贡献者与插件作者的第一条命令不再失败 |
| 覆盖率阈值改为"不低于基线"，CI 输出失败清单 | P1 | 全绿 | 门禁不可再"带红通过" |
| 补 `pre-commit` + `.editorconfig` + 删 `black` | P2 | 无 | 减少"格式脏了"的无效评审 |

**预期收益**：项目从"能跑但有一处必现故障"回到"对外可交付"；把两处结构性风险（导入污染、门禁失真）在成本最低时处理掉。

### S2 · 结构收敛（1–2 月）

| 目标 | 优先级 | 依赖 | 预期收益 |
| --- | --- | --- | --- |
| 设置体系归一：`appcore/settings` 为唯一真相，`user_settings` 降为存储后端，`CSettingsDrawer` 改为复用 `SchemaPage` 子集；删 `CSettingsPanel` | P1 | S1 文档清理 | 新增设置项从"改 3–4 处"降到"改 1 处"；消除"设置不生效"类 bug |
| 依赖边界定案：方案 A（数据注入断开 `guicore → gallery`）或方案 B（改文档并承认平台层）；守卫改 5×5 白名单 | P1 | 无 | 组件库可独立复用（或叙事诚实）；重构影响面可静态推导 |
| `plugin_store.py` 三段拆分；5 个自绘件上移或组件库化 | P1 | 依赖边界定案 | 主题/令牌升级能覆盖插件生态入口页 |
| 菜单族收敛：`CPopupMenu` 为唯一新实现，其余标注弃用，`COMPONENTS.md` 加决策表 | P2 | 无 | 插件作者不再面对 10 选 1 |
| `MainWindowController` / `SettingsController` 合并或明确分工；引入 `Protocol` 收敛 `getattr` | P2 | 设置归一 | 跨层调用可静态检查 |
| `guicore.__all__` 分域；兼容壳加 `DeprecationWarning` | P2 | 无 | 3.0 的破坏性变更有清晰路径 |
| mypy `files` 扩到 `gallery/*`（插件契约面） | P2 | 无 | 插件 API 的类型承诺开始成立 |

**预期收益**：把"网状依赖"收敛回"分层"；把三套并行的设置实现压成一套；这两个动作合计预计能消掉后续 30–40% 的"改一处、坏一处"类问题。

### S3 · 平台化（1 季度）

| 目标 | 优先级 | 依赖 | 预期收益 |
| --- | --- | --- | --- |
| 插件服务注册表 + 插件级事件总线（`ctx.services.register(name, obj)` / `ctx.events.subscribe`） | P1 | S2 依赖定案 | 打开"插件组合"生态：A 提供数据源、B 提供视图，无需重复实现 |
| 视觉回归基线（离屏 `grab()` + 感知哈希） | P1 | `showcase` 可用 | 替代 592 行人工清单中的视觉部分，主题/组件改动敢合 |
| 跨平台外壳（macOS/Linux 圆角与窗口控件；亚克力降级为不透明） | P2 | 无 | `OS Independent` 分类器名实相符 |
| 冻结形态能力矩阵（launcher / wheel / PyInstaller 三形态的"能做什么"表）+ `sys.frozen` 分支 | P2 | RV-13 | 宿主集成不再踩"插件依赖装不上"的坑 |
| 插件进程隔离（`EXT-01`） | P3 | 服务注册表、事件总线（否则 IPC 协议无从定义） | 打开公开市场的唯一前提 |
| 文档站/API 自动生成（从 `__all__` + docstring） | P3 | 分域 `__all__` | 文档数字漂移从机制上消除 |

**预期收益**：从"好用的组件基座"变成"可承载第三方生态的插件平台"；这也是 `PLUGIN.md`/`GALLERY.md` 已经在讲、但能力上还没闭环的故事。

---

## 6. 附：关键证据索引

| 结论 | 复核命令 |
| --- | --- |
| 用例失败 | `uv run pytest tests/test_showcase.py -x` |
| 覆盖率 71% | `uv run pytest --cov=sllkgui --cov-report=term` |
| 类型门禁仅 4 文件 | `grep -A6 "\[tool.mypy\]" pyproject.toml` |
| 公开名 160 / 105 | `python -c "import ast,pathlib;..."`（统计 `__all__` 长度） |
| 依赖矩阵 | AST 扫 `src/sllkgui/**/*.py` 的 `Import`/`ImportFrom`，区分模块级与函数内 |
| `appcore` 拉 Qt | `uv run python -c "import sys,sllkgui.appcore; print('PySide6.QtGui' in sys.modules)"` |
| `data` 从未实现 | `git log --all --oneline -- src/sllkgui/showcase/core_preview/surfaces/data`（空） |
| 示例插件合规 | `uv run sllkgui plugin lint examples/plugin-hello` |
| 文档漂移 | `grep -rn "apps/" docs/*.md README.md` |
