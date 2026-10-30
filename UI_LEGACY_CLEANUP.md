# UI 层历史遗留整改清单

> 生成日期：2026-10-13
> 范围：针对 2026-10-13 代码评估中发现的 UI 层历史遗留问题，记录已修复项与待办项。
> 状态口径：`[已修复]` = 本次已完成并通过 pytest（128 passed）+ ruff 验证；`[待办]` = 尚未处理。

---

## 一、已修复（本次完成）

### 1. QSS 资源路径硬编码 + 大小写不一致 + CWD 依赖 ［已修复］

**问题**：`GuiCore/styles.py` 与 `GuiCore/CustomUI/button/menu_btn.py` 的 QSS 中硬编码
`url(resource/CustomUI/...)`（大写 `CustomUI`），磁盘实际目录为小写 `customui`。
Windows 文件系统大小写不敏感故侥幸可用；但：

- Linux / macOS 下资源将全部加载失败（含 fallback 图标路径，同样大写）；
- QSS `url()` 相对**当前工作目录**解析，从任意目录启动（含打包 exe）时图标丢失，
  与项目「独立于工作目录」的设计承诺冲突（现有测试仅用 AST 禁止 `os.getcwd`，拦不住 QSS 路径）。

**修复内容**：

| 文件 | 修改 |
| --- | --- |
| `AppCore/SYS/other/static_func.py` | 5 处资源目录类属性 `resource/CustomUI/*` → `resource/customui/*` |
| `AppCore/SYS/module/logger_module.py` | `resource/CustomUI/settings/console.yaml` → 小写 |
| `AppCore/SYS/module/plugin_module.py` | `resource/CustomUI/settings/plugins.yml` → 小写 |
| `GuiCore/styles.py` | 4 处 QSS `url(resource/CustomUI/...)` → `PathFactory.set_svg_icon()` 生成绝对路径（正斜杠） |
| `GuiCore/CustomUI/button/menu_btn.py` | 2 处 QSS `url(...)` 改为模板占位符，`set_stylesheet()` 时注入绝对路径 |
| `tests/test_path_resolution.py` | 2 处测试路径同步小写化 |

**验证**：从任意目录（`%TEMP%`）启动后：
- `PathFactory.set_svg_icon("icon_arrow_right")` 解析到存在的绝对路径；
- 全局样式内 4 处 `url()` 全部为绝对路径（正斜杠、小写 `customui`）且文件存在；
- `pytest` 128 passed；`ruff check .` All checks passed。

---

### 2. 死代码清理 ［已修复］

| 位置 | 内容 | 处理 |
| --- | --- | --- |
| `Guis/windows/main_window/setup_main_window.py` | `load_page2()` 整段未被调用的历史页面（约 80 行硬编码中文，与 `Apps/welcome` 重复） | 删除方法 + 同步清理 13 个因此失引用的 import |
| `main.py` | 约 20 行被注释的 QSystemTrayIcon 托盘代码（引用已不存在的 `loading_window.loader.sys_config`） | 删除注释块 |
| `Guis/windows/main_window/ui_main.py` | 右列背景被注释的 setObjectName/setStyleSheet 块 | 删除注释块 |

**验证**：`pytest` 128 passed；`ruff check .` All checks passed（含 F401 未使用导入检查）。

---

## 二、待办项（建议后续处理，按优先级排序）

### P1 主题颜色构造时快照（违反项目自身约定）

- **位置**：`GuiCore/WindowDefineUI/title_bar/title_bar.py` 构造时读取
  `ColorPalette.custom_dark_one / custom_dark_three / ...` 存入实例变量；
  `GuiCore/WindowDefineUI/title_bar/title_button.py` 初始 `_set_icon_color` 同理。
- **问题**：README 明确约定「自绘组件在 paintEvent 中实时读取 ColorPalette（禁止构造时快照）」。
  全局样式表可覆盖主框架背景，但按钮图标色、分割线色等内部取值在主题切换后不刷新，
  主题热切换可能出现新旧配色混搭。
- **建议**：组件订阅 `get_theme_manager()`，在回调中更新实例色值并 `update()`；
  或 paintEvent 内实时读取 `ColorPalette`。

### P2 配置声明不一致

- **位置**：`pyproject.toml` 中 `[tool.ruff] target-version = "py312"`，
  而 `requires-python = ">=3.13"`、`.python-version` 为 3.13。
- **影响**：ruff 按 py312 语法目标检查，无法发现 3.13 专属语法误用；声明互相矛盾。
- **建议**：统一为 `target-version = "py313"`（或与 requires-python 保持一致的版本）。

### P3 Git 索引中间态（plugins → Apps 迁移未收敛）

- **现象**：`git status` 显示 `plugins/example/...` 等路径为 `AD`
  （索引已添加删除、工作区已删），新 `Apps/` 目录尚未全部加入索引。
- **风险**：后续提交可能把旧路径残留带进历史，或误删新文件。
- **建议**：确认无误后执行 `git add -A` 一次性收敛；若需保留历史，先 `git mv` 迁移再提交。

### P4 零散注释残留（低优先级）

- `GuiCore/WindowDefineUI/title_bar/title_bar.py`：`# self.top_logo.setPixmap(...)` 等 4 处行内注释；
- `GuiCore/CustomUI/button/menu_btn.py`：`# self.set_stylesheet(...)` 被注释调用块；
- `GuiCore/WindowDefineUI/grips/grips.py` 等可能存在的类似残留（未逐一排查）。
- **建议**：随手清理，不影响运行，纯整洁度收益。

---

## 三、验证方式与覆盖范围

| 项 | 结果 |
| --- | --- |
| `pytest -q` | 128 passed（1.35s） |
| `ruff check .` | All checks passed |
| 任意目录启动资源解析 | 通过（模拟 `chdir(%TEMP%)` 后 QSS 与 PathFactory 均解析到存在的绝对路径） |
| 未覆盖 | 未做真实 GUI 启动冒烟（依赖 Qt 事件循环与显示环境）；`load_page2` 删除前确认全仓无引用（grep 仅定义处 1 处） |

> 说明：`GuiCore.CustomUI`（Python 包名，磁盘目录本身为大写 C）与 `setObjectName("CustomUI")`、
> `registry.py` 中 `return "CustomUI"`（品牌名/对象名）不属于资源路径，本次未改动。
