# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。`0.x` 阶段 minor 版本可能含
破坏性变更，均在下方显式列出。

## 0.3.0

这次是**结构性重构**：目录、包名、导入路径全变。老代码需要按下面「迁移指南」调整。

### 破坏性变更

| 变更 | 之前 | 现在 |
| --- | --- | --- |
| 包布局 | 仓库根四个顶层包 `AppCore/` `GuiCore/` `Guis/` `customgui/` | 单包 `src/customgui/{appcore,guicore,guis}` |
| 子包命名 | `SYS` `APP` `Tool` `CustomUI` `WindowDefineUI` `AppDefineUI` | `sysx` `app` `tool` `custom_ui` `window` `app_ui` |
| 资源位置 | `customgui/resource/` | `src/customgui/_resources/` |
| 应用目录 | `Apps/` | `apps/` |
| 示例入口 | `main.py` | `examples/hello_world/main.py` |
| 应用模块命名空间 | `customgui_apps.<name>` | `_customgui_apps.<name>`（私有，消费方改用 `load_app_handles()`） |
| `Ui_LeftColumn` / `Ui_RightColumn` 实现位置 | `guis/columns/` | `guicore/window/{left,right}_column/ui.py`（对外名字不变） |

**移除**：`AppCore.Tool` 的死文件、`appcore/app/app_loader.py`（0 字节）、2483 个未被引用的 SVG（移到 `docs/icons/library/`）。

### 新增

- **`customgui.window` 门面**：`UiMainWindow` / `SetupMainWindow` / `MainWindowController` /
  `load_apps` / `load_app_handles` / `get_app_handle` / `AppHandle` / `apply_language` ……
  宿主应用只认这一个模块，不必再碰内部装配层。
- **`customgui.configure()`**：用一次调用取代 5 个 `CUSTOMGUI_*` 环境变量；环境变量降级为兜底，
  且**不再要求「必须在 import 之前设置」**。配置已加载后再调会抛 `ConfigAlreadyLoadedError`。
- **`customgui` 命令行**：`run` / `install-demo` / `examples` / `doctor`。
- **`customgui doctor`**：一条命令打印版本、资源根、数据根、应用目录、发现到的应用、当前主题与语言。
- **`AppHandle`**：`load_app_handles()` 返回 `list[AppHandle]`，消费方按名字取模块，不再拼私有命名空间路径。
- **内置示例随 wheel 分发**：`apps/` 与 `examples/hello_world/` 打进包内，`install-demo` / `examples --copy` 开箱可用。
- **`py.typed`**（PEP 561）。

### 修复

- **资源根语义分裂**：基座包内资源在 `_resources/customui/`，应用覆盖资源在 `<root>/resource/customui/`，
  而代码里写的是 `resource/customui/...`。`resource_roots()` 现在统一到「其下有 `customui/`」这一层，
  并兼容旧的 `resource/xxx` 写法，装成 wheel 后主题/语言/设置不再全部丢失。
- **`apps_root()`** 在 src layout 下解析到 `src/apps`（不存在），改为按
  `data_root/apps` → 仓库根 `apps/` → `src/apps` → 包内 `apps/` 依次探测。
- **应用内跨目录相对导入**：`<app>/lib/__init__.py` 里的 `from ..calc import add` 以前必失败，
  现在由 `_namespace` MetaPathFinder 兜住。
- **`guicore → guis` 层级倒挂**：`CLeftColumn` 不再反向 import 装配层。
- **`static_func` 循环导入**（ruff 整理 import 时暴露）。
- **两个假绿测试**：`test_no_cwd_runtime_dependency.py` 与 `test_architecture_boundaries.py` 在 src layout
  下扫的是不存在的目录，`rglob` 空转、断言永远通过。已修正路径并加「一个文件都没扫到就报错」的自检。

### 新增架构守卫（`tests/test_architecture_boundaries.py`）

1. `appcore` 不得 import `guicore` / `guis`
2. `guicore` 不得 import `guis`
3. `guis` / `guicore` 只能使用 `appcore` 公开面，禁止 `appcore.sysx.*` 深层导入
4. 伪造应用命名空间必须私有（`_customgui_apps`）
5. 禁止 `Path(__file__).resolve().parents[N]`（N ≥ 2）

### 迁移指南

```diff
- from AppCore import AppSettings, ColorPalette, Language, get_app_context
+ from customgui.appcore import AppSettings, ColorPalette, Language, get_app_context

- from Guis import SetupMainWindow, UiMainWindow
+ from customgui.window import SetupMainWindow, UiMainWindow

- from Guis.windows.main_window.controller import MainWindowController
+ from customgui.window import MainWindowController

- os.environ["CUSTOMGUI_APPS_DIR"] = "./Apps"
+ import customgui; customgui.configure(apps_dir="./apps")
```

测试：`165 passed` → **`270 passed, 5 skipped`**。

## 0.2.4

PyCL2 基座同步：懒加载页面、主题强调色覆盖、信号 sender 修复、语言订阅清理。
详见 `docs/PYCL2_BASE_SYNC.md`。
