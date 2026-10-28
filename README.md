# CustomGUI · PySide6

<p align="center">
  <img src="ReadMeRes/概览.png" alt="CustomGUI 概览" width="900">
</p>

<p align="center">
  基于 <b>PySide6</b> 的桌面 UI 基座：主题、组件、窗口框架、插件加载、配置与语言系统。
</p>

<p align="center">
  <a href="https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python">Gitee</a> ·
  <a href="https://github.com/shilianlvke/CustomGUI_Qt_For_Python">GitHub</a> ·
  <a href="Docs/README.md">组件文档</a> ·
  <a href="Docs/ARCHITECTURE.md">架构说明</a>
</p>

---

## 简介

**CustomGUI** 是一个可直接运行、也可作为依赖安装的 PySide6 UI 基座。

它提供：

- 无边框圆角窗口、自绘标题栏、左侧菜单、左右列与底部版权栏；
- 统一设计令牌的颜色、字体、间距、圆角和尺寸；
- 完整组件库：按钮、输入框、下拉框、卡片、菜单、滚动区、提示框等；
- YAML 配置系统：主题、语言、窗口设置、控制台设置；
- 应用模组协议：把页面作为 `Apps/<name>/` 插件加载；
- 页面懒加载、语言切换重建、主题切换、遥测和诊断；
- 可安装的 `customgui` wheel，基座资源随包分发。

Demo 启动后可以直接看到完整窗口和内置组件/页面示例。

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10/11（主要支持），Linux/macOS 理论可用 |
| Python | **3.12+** |
| GUI | PySide6 **6.10+** |
| 配置 | PyYAML |
| 依赖管理 | [uv](https://docs.astral.sh/uv/) |

---

## 安装

### 方式一：作为依赖安装

适合把 CustomGUI 作为另一个应用的基座。

```powershell
uv add "customgui @ git+https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python.git@base-v0.2.4"
```

或固定到某个提交：

```toml
[tool.uv.sources]
customgui = {
    git = "https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python.git",
    rev = "548d992",
}
```

### 方式二：从源码运行 Demo

```powershell
git clone https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python.git
cd CustomGUI_Qt_For_Python
uv sync --extra dev
uv run python main.py
```

### 方式三：构建 wheel

```powershell
uv build --wheel
```

产物：

```text
dist/customgui-0.2.4-py3-none-any.whl
```

wheel 包含：

```text
AppCore/
GuiCore/
Guis/
customgui/
  resource/
```

不包含 Demo 的 `Apps/`、测试和文档截图。

---

## 快速开始

### 作为宿主应用使用

```python
import os
from pathlib import Path

# 可选：指定业务插件、应用覆盖资源和可写数据目录
os.environ.setdefault("CUSTOMGUI_APPS_DIR", str(Path(__file__).parent / "Apps"))
os.environ.setdefault("CUSTOMGUI_RESOURCE_DIR", str(Path(__file__).parent))
os.environ.setdefault("CUSTOMGUI_DATA_DIR", str(Path.home() / ".my-app"))

from PySide6.QtWidgets import QApplication
from AppCore import AppSettings, ColorPalette, Language, AppThemes, AppLanguages, get_app_context
from Guis import SetupMainWindow, UiMainWindow
from Guis.windows.main_window.controller import MainWindowController

get_app_context()
ColorPalette.update(AppThemes[AppSettings.theme_name].data)
Language.update(AppLanguages[AppSettings.language].data)
```

窗口装配涉及 grips、标题栏、控制器和首屏页面，完整可运行示例请直接参考
[`main.py`](main.py)；上例只展示资源与配置初始化顺序。

### 运行 Demo

```powershell
uv run python main.py
```

Demo 会从仓库的 `Apps/` 加载 9 个示例应用，并只创建默认页面；其他页面首次导航时加载。

---

## 目录结构

```text
CustomGUI_Qt_For_Python/
├── AppCore/                    # 配置、语言、主题、插件、日志、遥测
│   ├── APP/
│   ├── SYS/
│   └── Tool/
├── GuiCore/                    # 窗口与组件实现
│   ├── AppDefineUI/
│   ├── CustomUI/
│   ├── WindowDefineUI/
│   └── styles.py
├── Guis/                       # 窗口装配、插件加载、页面路由
│   ├── app_loader.py
│   ├── language_service.py
│   ├── columns/
│   └── windows/
├── customgui/                  # 可安装资源包
│   ├── __init__.py
│   └── resource/customui/
│       ├── images/
│       ├── languages/
│       ├── settings/
│       └── themes/
├── Apps/                       # Demo 插件（不进入 wheel）
├── Docs/                       # API / 架构 / 兼容性文档
├── tests/                      # 165+ 基座测试
├── main.py                     # Demo 入口
└── pyproject.toml
```

---

## 资源与环境变量

基座默认资源位于：

```text
customgui/resource/customui/
```

宿主应用可以增加一层覆盖资源，只要目录内同样包含 `resource/customui/`：

```text
MyApp/
└── resource/
    └── customui/
        ├── images/
        ├── languages/
        ├── settings/
        └── themes/
```

查找优先级：

```text
CUSTOMGUI_RESOURCE_DIR 资源
CUSTOMGUI_ROOT_DIR     资源
customgui 包内置资源
```

支持的环境变量：

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `CUSTOMGUI_APPS_DIR` | 应用模组目录 | 项目根目录 `Apps/` |
| `CUSTOMGUI_RESOURCE_DIR` | 覆盖资源根目录 | 无 |
| `CUSTOMGUI_ROOT_DIR` | 兼容旧项目的根目录覆盖 | 基座包推导 |
| `CUSTOMGUI_DATA_DIR` | 日志等可写数据根 | `%APPDATA%/CustomGUI` |
| `CUSTOMGUI_DIAGNOSTICS_DIR` | 遥测 JSON 目录 | `DATA_DIR/logs/diagnostics` |

> 安装后的基座不会向 `site-packages` 写日志；所有可写数据都进入 `CUSTOMGUI_DATA_DIR`。

---

## 配置系统

配置位于 `customgui/resource/customui/` 或宿主的覆盖资源目录，采用 YAML + 类型化 Schema。

| 目录 | 加载方式 | 入口 |
| --- | --- | --- |
| `settings/` | 目录内所有 YAML 深度合并 → 强类型校验 | `AppSettings` |
| `themes/` | 每个文件独立加载并校验 | `AppThemes` |
| `languages/` | 每个文件独立加载并校验 | `AppLanguages` |
| `others/` | 每个文件独立加载 | `AppOthers` |

```python
from AppCore import AppSettings, AppThemes, AppLanguages, get_app_context

get_app_context()

AppSettings.theme_name
AppSettings.startup_size
AppSettings.lef_menu_size.minimum
AppThemes[AppSettings.theme_name].data
AppLanguages[AppSettings.language].data
```

### 新增主题

在覆盖资源目录放一个 YAML：

```text
resource/customui/themes/my_theme.yaml
```

文件名即主题名，加载时自动校验颜色字段。

### 新增语言

```text
resource/customui/languages/ja_jp.yaml
```

至少包含：

```yaml
custom_ui: {}
PAGE: {}
UI: {}
```

> 基座默认只带 `zh_cn` / `en_us`。语言列表由应用实际提供的文件决定更稳妥，详见
> [Docs/PYCL2_BASE_SYNC.md](Docs/PYCL2_BASE_SYNC.md)。

---

## 应用模组

基座本身不强制包含业务页面。页面由 `Apps/` 下的应用模组提供：

```text
Apps/<app_name>/
├── config.yml
├── resource/
│   ├── icon/app_icon.svg
│   └── lang/{zh_cn,en_us}.yml
└── gui/
    ├── main.py
    └── style.py
```

三种页面协议（按优先级）：

```python
# 1. 自由注册多个页面
def register_plugins(registry, app):
    ...

# 2. PAGE 对象
class MyPage:
    def load_page(self):
        ...

PAGE = MyPage

# 3. 最简 build_page
def build_page(app):
    ...
    return widget
```

`config.yml` 常用字段：

| 字段 | 说明 |
| --- | --- |
| `app_name` / `app_id` | 应用名与插件 ID |
| `button_id` / `page_object` | 导航键与页面对象名 |
| `app_target` | `LeftMenu` 或 `TitleMenu` |
| `is_default` | 是否默认页 |
| `show_top` / `is_active` | 菜单位置与默认激活 |

应用可以通过 `app.config`、`app.icon`、`app.image`、`app.lang_text()` 访问自己的清单和资源；应用目录内部的相对导入也由加载器自动建立包结构。

### 页面懒加载

- 启动时只创建默认页；
- 导航到新页面时才调用页面 loader；
- 语言切换只重建当前页；
- 页面注册/查找通过 `Guis.windows.main_window.registry` 完成。

这避免了“启动时实例化全部隐藏页面”和“切换语言重建所有页面”的开销。

---

## 组件

组件位于 `GuiCore/CustomUI/` 与 `GuiCore/WindowDefineUI/`，包括：

- `CPushButton`、`CStatusButton`
- `CLineEdit`、`CComboBox`
- `CCard`、`CShowCard`
- `CMenu`、`CMenuButton`
- `CScrollArea`
- `CLeftMenu`、`CLeftColumn`
- `CTitleBar`、`CWindow`
- `CToolTip`
- `CDialog`

**下拉框不使用原生 `QComboBox`**：`CComboBox` 使用自绘圆角弹层，避免 Windows 原生弹层黑角。

完整 API 见 [Docs/API.md](Docs/API.md)。

---

## 设计令牌

颜色、字体、间距、圆角、边框和尺寸统一由 `GuiCore.styles` 与 `AppCore.DesignTokens` 提供：

```python
from AppCore import get_design_tokens

tokens = get_design_tokens()
tokens.colors.surface_card
tokens.radius.window
tokens.size.control_height
```

主题颜色在 `themes/*.yaml`，几何值在组件本地默认值与设计令牌中维护，避免样式散落。

---

## 打包与发布

基座 wheel：

```powershell
uv build --wheel
```

在宿主应用中使用 PyInstaller 时，需要收集包内资源：

```python
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("customgui")
```

如果宿主只安装 wheel，不携带 `Apps/`，请通过 `CUSTOMGUI_APPS_DIR` 指向自己的插件目录。

---

## 测试与质量

```powershell
uv run pytest
uv run ruff check AppCore GuiCore Guis customgui
```

当前测试覆盖：

- 配置加载与类型校验；
- 路径与资源覆盖；
- 语言服务；
- 页面注册/路由/懒加载；
- 插件协议；
- 主窗口控制器；
- 设计令牌与组件几何；
- 主题切换与遥测；
- 错误边界。

---

## 许可证与致谢

- 代码许可证：[木兰宽松许可证，第 2 版](LICENSE)。
- 设计灵感：[PyOneDark](https://github.com/Wanderson-Magalhaes/PyOneDark_Qt_Widgets_Modern_GUI)。
- 基座在 [Gitee](https://gitee.com/shilianlvke/CustomGUI_Qt_For_Python) 与 [GitHub](https://github.com/shilianlvke/CustomGUI_Qt_For_Python) 开源。

> `PyCL2` 是使用本基座构建的 Minecraft 启动器示例，二者的业务代码和品牌资源保持独立。
