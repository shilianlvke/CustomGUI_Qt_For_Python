# CustomGUI · PySide6

<p align="center">
  <img src="docs/assets/概览.png" alt="CustomGUI 概览" width="900">
</p>

<p align="center">
  基于 <b>PySide6</b> 的桌面 UI 基座：主题、组件、窗口框架、插件加载、配置与语言系统。
</p>

<p align="center">
  <a href="https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python">Gitee</a> ·
  <a href="https://github.com/shilianlvke/CustomGUI_Qt_For_Python">GitHub</a> ·
  <a href="docs/README.md">组件文档</a> ·
  <a href="docs/ARCHITECTURE.md">架构说明</a> ·
  <a href="CHANGELOG.md">更新日志</a>
</p>

---

## 这是什么

**CustomGUI** 是一个基于 PySide6 的 UI 基座。它替你写好了一个桌面应用开局就要面对的
那堆脏活：

- 无边框圆角窗口、自绘标题栏、可折叠左列/左菜单、底部版权栏、拖拽缩放；
- 一套设计令牌（颜色/字体/间距/圆角/尺寸）驱动的统一样式，切换主题自动生效；
- 70 个组件：按钮、输入框、下拉、日期、卡片、徽章、抽屉、Toast、气泡确认……
- YAML 配置系统：主题、语言、窗口设置、日志；
- **目录即插件**：把页面放进 `apps/<name>/`，启动时自动发现、注册菜单、懒加载；
- 语言切换重建页面、遥测与诊断、错误边界。

它不是脚手架，也不是组件库 demo——是一个**能装进别的项目当依赖**的基座。

---

## 安装

### 当作依赖装进你自己的项目

```powershell
uv add "customgui @ git+https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python.git@base-v0.5.1"
```

固定到具体 tag 而不是分支，避免上游改动把你的构建搞红。

### 从源码跑（想改基座本身）

```powershell
git clone https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python.git
cd CustomGUI_Qt_For_Python
uv sync --extra dev
uv run customgui run
```

### 构建 wheel

```powershell
uv build --wheel
uv run twine check dist/*.whl
```

产物 `dist/customgui-0.5.1-py3-none-any.whl`（约 257 个包内文件），包含：

```text
customgui/
├── appcore/          # 逻辑层：配置、主题、语言、令牌、插件协议、错误边界、工具
├── guicore/          # 组件层：custom_ui（组件库）+ window（窗口部件）+ app_ui
├── guis/             # 装配层：主窗口、页面栈、插件加载、语言服务
├── _resources/       # 只读默认资源：主题/语言/图标/设置四套 YAML
├── apps/             # 5 个内置示例应用（供 customgui install-demo 使用）
├── examples/         # 最小可运行工程（供 customgui examples --copy 使用）
├── cli.py            # 命令行入口
├── window.py         # 窗口装配门面（宿主应用只认这个）
├── config.py         # configure() 显式配置
└── py.typed          # PEP 561 类型标记
```

---

## 30 秒上手

装完之后不需要读文档，两条命令就能看到东西：

```powershell
customgui install-demo     # 把 5 个示例应用拷到数据目录
customgui run              # 起窗口
```

如果窗口是空的，或者想确认环境对不对：

```powershell
customgui doctor
```

```text
CustomGUI doctor
========================================================
✓ 版本          : 0.5.1
✓ 包目录        : .../site-packages/customgui
✓ 资源根 #0     : .../site-packages/customgui/_resources
✓ 数据根        : ~/.customgui
✓ 应用目录      : ~/.customgui/apps
--------------------------------------------------------
发现应用      : 5 个
  - button_preview
  - feedback_preview
  - input_preview
  - overlay_preview
  - panel_preview
成功加载      : 5 个
  + button_preview  ->  _customgui_apps.button_preview.gui.main
  ...
--------------------------------------------------------
✓ 当前主题      : default（共 4 套）
✓ 当前语言      : zh_cn（共 2 种）
```

把这段输出贴给维护者，比描述「我的窗口是黑的」有用一百倍。

### 命令行一览

| 子命令 | 作用 |
| --- | --- |
| `customgui run [--apps-dir DIR] [--data-dir DIR]` | 启动主窗口 |
| `customgui install-demo [--dest DIR] [--force]` | 安装内置示例应用到 `<data_root>/apps` |
| `customgui examples [--copy DIR]` | 导出最小可运行工程骨架 |
| `customgui doctor [--apps-dir DIR]` | 打印全部路径与发现结果 |

---

## 写一个自己的应用

```powershell
customgui examples --copy ./myapp
cd myapp
python main.py
```

导出的 `main.py` 就是下面这个样子——这就是一个完整可运行的 CustomGUI 应用：

```python
"""myapp/main.py —— 最小可运行的 CustomGUI 应用。"""
import sys
from pathlib import Path

import customgui
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from customgui.appcore import AppLanguages, AppSettings, AppThemes, ColorPalette, Language, PathFactory, get_app_context
from customgui.window import MainWindowController, SetupMainWindow, UiMainWindow, load_apps

ROOT = Path(__file__).resolve().parent

# 一行取代 5 个环境变量；顺序也不再重要（不必卡在 import 之前）
customgui.configure(
    apps_dir=ROOT / "apps",          # 业务插件目录
    data_dir=ROOT / ".data",         # 可写数据（日志、遥测）
    builtin_menus=False,             # 不需要基座自带的「软件信息」菜单
)


def main() -> int:
    get_app_context()                                     # 配置上下文（惰性，也可省略）
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon = PathFactory.set_ico(AppSettings.logo)
    if icon and Path(icon).is_file():
        app.setWindowIcon(QIcon(icon))

    load_apps()                                           # 发现并注册 apps/ 下全部应用

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("CustomUI")
            self.setMouseTracking(True)
            self.resize(*AppSettings.startup_size)
            self.setMinimumSize(*AppSettings.minimum_size)
            self.ui = UiMainWindow()
            self.ui.setup_ui(self)
            SetupMainWindow.setup_gui(self)
            self.controller = MainWindowController(self)
            self.show()

        def btn_clicked(self):
            btn = SetupMainWindow.setup_btns(self)
            if btn is not None:
                self.controller.handle_button(btn)

        def btn_released(self):
            SetupMainWindow.setup_btns(self)

        def resizeEvent(self, event):
            SetupMainWindow.resize_grips(self)

        def mousePressEvent(self, event):
            self.dragPos = event.globalPosition().toPoint()
            self.focusNextChild()

    window = MainWindow()   # noqa: F841 - 需要保持引用
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
```

---

## 应用插件协议

应用就是 `apps/` 下的一个目录，**自包含**、不用改基座代码：

```text
apps/<app_name>/
├── config.yml                     # 清单：app_name / button_id / page_object / app_icon / is_default ...
├── resource/
│   ├── icon/app_icon.svg          # 菜单图标
│   └── lang/{zh_cn,en_us}.yml     # 本应用语言文本
└── gui/
    ├── main.py                    # 页面实现（三选一协议）
    └── style.py                   # 可选：应用私有样式
```

`gui/main.py` 里实现以下三种之一即可（按优先级识别）：

| 协议 | 写法 | 适用 |
| --- | --- | --- |
| **1. register_plugins** | `def register_plugins(registry, app)` | 多页面应用，完全自由 |
| **2. PAGE** | `PAGE = MyPage()`（含 `load_page(window)`） | 与基座历史页面风格一致 |
| **3. build_page** | `def build_page(app) -> QWidget` | 最简，一个页面一个函数 |

```python
# apps/hello/gui/main.py —— 协议 3，最简单的一种
from PySide6.QtWidgets import QLabel, QWidget


def build_page(app):
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "helloPage")
    label = QLabel(app.lang_text("app_text", "你好"))
    label.setParent(page)
    return page
```

`app` 是 `AppContext`，提供：`config`（清单字段）、`app_dir`、`icon_path`、
`lang_text(key)`、`resource(*parts)` / `icon()` / `image()` / `lang_file()`。

> 应用内部的相对导入是支持的：`gui/main.py` 里 `from ..lib import helper` 会
> 落到 `<app>/lib/`，`<app>/` 下任意子目录都能这样互相引用。

---

## 配置：`configure()` 与环境变量

**推荐显式调用**：

```python
import customgui

customgui.configure(
    apps_dir="./apps",                    # 应用插件目录
    resource_dirs=["./brand"],            # 覆盖资源（其下有 customui/ 或 resource/customui/）
    data_dir="~/.myapp",                  # 可写数据根
    diagnostics_dir="~/.myapp/diagnostics",
    builtin_menus=False,                  # 是否注入基座自带菜单
)
```

优先级：**显式参数 > `CUSTOMGUI_*` 环境变量 > 内置默认值**。

环境变量仍然可用（旧项目不用改），但**顺序不再是硬性要求**——不再需要
「必须在 import customgui 之前设好」。

| 环境变量 | 作用 | 默认 |
| --- | --- | --- |
| `CUSTOMGUI_APPS_DIR` | 应用插件目录 | 自动探测 `data_root/apps` → 仓库根 `apps/` |
| `CUSTOMGUI_RESOURCE_DIR` | 覆盖资源根（其下有 `resource/` 或 `customui/`） | 无 |
| `CUSTOMGUI_ROOT_DIR` | 旧版覆盖根（兼容保留） | 无 |
| `CUSTOMGUI_DATA_DIR` | 可写数据根（日志、遥测） | `%APPDATA%/CustomGUI` 或 `~/.customgui` |
| `CUSTOMGUI_DIAGNOSTICS_DIR` | 诊断事件目录 | `<data>/logs/diagnostics` |
| `CUSTOMGUI_BUILTIN_MENUS` | `0` 关闭基座自带菜单 | 开 |

配置上下文已加载后再调 `configure()` 会**直接抛 `ConfigAlreadyLoadedError`**，
而不是静默失效——要么在 `get_app_context()` 之前调用，要么传 `force_reload=True`。

### 资源层：配置逐层合并，其他资源整份替换

资源根按优先级排列：`configure(resource_dirs=...)` / 环境变量 → 各应用的品牌层
`<app>/brand/` → 基座包内默认资源。

- **配置（`settings/` / `themes/` / `languages/`）逐层深合并**：高优先级层只需写
  要改的键，其余键继续由基座提供。品牌层的 `window.yaml` 只写三行也能跑，基座
  以后新增设置项不会因为「覆盖层缺键」而在启动时校验失败。
- **其他资源（图标、图片、字体）同名文件按优先级取第一份**，即整份替换。

`iter_files()` 给的是「每个文件名只要最高优先级那份」的视图（发现、存在性判断用）；
需要拿到所有层自己合并时用 `iter_file_layers()`，它返回
`{相对路径: (低优先级, ..., 最高优先级)}`。

---

## 目录结构

```text
CustomGUI_Qt_For_Python/
├── src/customgui/                    # ← 唯一的 Python 包（src layout）
│   ├── appcore/                      # 逻辑层（不依赖任何 UI）
│   │   ├── sysx/
│   │   │   ├── config/               # 配置注册表、YAML IO、路径解析、schema 校验
│   │   │   ├── modules/              # 主题、语言、插件协议、日志、遥测、错误边界
│   │   │   ├── handlers/             # YAML 读写
│   │   │   └── common/               # 路径/图标工厂
│   │   ├── app/                      # 主窗口用例（与 Qt 解耦的业务编排）
│   │   └── tool/                     # 设备等杂项工具
│   ├── guicore/                      # 组件层
│   │   ├── custom_ui/                # 40+ 组件（按钮/输入/卡片/浮层/反馈/展示…）
│   │   ├── window/                   # 标题栏、左菜单、左列、右列、grips、版权栏
│   │   ├── app_ui/                   # 对话框等应用级 UI
│   │   └── styles.py                 # 设计令牌 → QSS 生成
│   ├── guis/                         # 装配层
│   │   ├── windows/                  # 主窗口 / 登录窗 / 加载窗
│   │   ├── pages/                    # 页面栈容器
│   │   ├── app_loader.py             # 应用插件发现与装载
│   │   └── language_service.py       # 语言整体切换 + 页面重建
│   ├── _resources/customui/          # 只读默认资源（随 wheel 分发）
│   │   ├── themes/  languages/  settings/  images/  others/
│   ├── window.py                     # ★ 宿主门面
│   ├── config.py                     # ★ configure()
│   ├── cli.py                        # ★ customgui 命令
│   └── py.typed
├── apps/                             # 内置示例应用（同时打进 wheel）
├── examples/hello_world/             # 最小可运行工程
├── tests/                            # 270 个测试
├── docs/                             # 组件文档、架构说明、截图
└── pyproject.toml
```

**分层规则**（有测试守着，不是口号）：

| 规则 | 断言 |
| --- | --- |
| `appcore` 不得 import `guicore` / `guis` | `test_architecture_boundaries.py` |
| `guicore` 不得 import `guis`（不准倒挂） | 同上 |
| `guis` / `guicore` 只能 `from customgui.appcore import <公开名>` | 同上 |
| 应用插件命名空间必须私有（`_customgui_apps`） | 同上 |
| 禁止 `Path(__file__).parents[N]`（N≥2） | 同上 |
| 运行时代码不得依赖 `os.getcwd()` | `test_no_cwd_runtime_dependency.py` |

---

## 组件库

`customgui.guicore` 导出 **73 个**公开名（70 个组件 + 3 个样式常量），全部由设计令牌驱动，主题切换即时生效：

| 分类 | 组件 |
| --- | --- |
| 按钮 | `CButton` `CPushButton` `CButtonGroup` `CSplitButton` `CStatusButton` `CMenuButton` `CToggleButton` |
| 输入 | `CLineEdit` `CInputText` `CTextarea` `CInputNumber` `CInputGroup` `CInputGroupAddon` `CFloatLabel` `CSelect` `CComboBox` `CListbox` `CMultiSelect` `CTreeSelect` `CAutoComplete` `CDatePicker` `CCalendarPanel` `CColorPicker` `CSlider` `CKnob` `CRating` |
| 选择 | `CCheckbox` `CRadioButton` `CSelectButton` `CToggleButton` `CToggleSwitch` |
| 展示 | `CCard` `CShowCard` `CPanel` `CBadge` `CChip` `CTag` `CAvatar` `CPixmap` `CProgressBar` `CSkeleton` `CDivider` `CHDiv` `CVDiv` `CBreadcrumb` `CSteps` `CPageTransition` |
| 浮层 | `CDrawer` `COverlayPanel` `CToolTip` `CMenu` |
| 反馈 | `CMessage` `CToast` `CConfirmDialog` `CDialog` |
| 布局 | `CTabs` `CAccordion` `CAccordionPanel` `CFieldset` `CFormField` `CFormGrid` `CScrollArea` `CSplitter` `CSplitterHandle` `CToolbar` |
| 窗口部件 | `CWindow` `CTitleBar` `CLeftMenu` `CLeftColumn` `CGrips` `CCredits` |
| 样式 | `Styles` `Severity` `Variant` |

主题与令牌：

```python
from customgui.appcore import get_design_tokens, get_theme_manager

tokens = get_design_tokens()
tokens.radius.window          # 圆角
tokens.color.primary          # 主色
get_theme_manager().apply("dark")
```

---

## 开发

```powershell
uv sync --extra dev
uv run pytest                 # 270 passed, 5 skipped
uv run ruff check src tests

uv run python -m build --wheel --no-isolation
uv run twine check dist/*.whl
```

提交前请读 [docs/contributing.md](docs/contributing.md)。有一条**硬规则**：
本项目是木兰宽松许可证 v2，**不得**把 GPL 项目（如 py-cl2）的业务代码搬进来，
否则整个仓库会变成 GPL 衍生物。

---

## 许可证

[木兰宽松许可证，第 2 版](LICENSE)（MulanPSL-2.0）。可商用、可闭源分发。
