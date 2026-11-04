# 更新日志

项目处于**内测阶段**（`0.x`），遵循[语义化版本](https://semver.org/lang/zh-CN/)的 `0.x` 约定：
minor 版本可能包含破坏性变更，均在本文件显式列出；patch 只做修复。

当前版本：`0.6.0`（见 `src/customgui/_version.py`），对应 tag `base-v0.6.0`。

---

## 未发布

### 外观配置

- 语言切换与主题配置合并为统一的“外观配置”模块，标题栏只保留一个色盘图标入口，
  移除独立的语言按钮；原 `btn_themes` 对象名保留以兼容既有接线。
- 语言改为在抽屉内直接选择目标语言，不再循环轮替；切换后抽屉标题、分区与
  菜单模式选项随语言同步刷新。
- 抽屉内部重排为“主题（含深色模式）/ 语言 / 菜单模式”三个分区，移除不可交互的
  “主色 / 表面色”示意色板与“仅作示意”说明。
- 清理壳层预览、菜单预览中的操作结果与点击回调状态文案，界面只保留面向用户的
  指引。

---

## 内测版 0.6.0（2026-11-04）

本次发布把窗口外观升级为 Windows 11 Fluent 亚克力风格，并将主题配置迁入右侧抽屉；
同时包含 `main` 分支此前积累、尚未单独发版的组件扩充。

### 界面与材质

- 新增 `guicore.acrylic`：通过 `SetWindowCompositionAttribute` 启用原生亚克力，附带 Win11
  圆角偏好与深色边框；非 Windows、Windows 10、RDP 与部分虚拟机自动回退为不透明。
- `CWindow` 在显示与主题切换时同步材质与色调，首次显示可淡入；新增
  `window.acrylic`（`enabled` / `opacity` / `fade_in`）配置段。
- 全局 QSS 改为分层玻璃表面（窗口 / 侧栏 / 面板 / 区域 / 卡片 / 控件 / 菜单），
  `default` / `bright` / `eye` 色板对齐 Fluent 中性色阶，`dracula` 保留原有紫色调。
- 自绘控件跟随玻璃材质：菜单按钮、标题栏按钮、输入族、面板/工具栏与骨架屏不再使用
  与 QSS 不一致的不透明底色；滑轨、骨架等写死颜色改为取调色板。
- 亚克力模式下禁用整窗 `QGraphicsDropShadowEffect`，主界面铺满窗口，去掉原本为投影
  预留的 10px 透明外圈；非亚克力环境仍保留外圈与窗口阴影。

### 主题配置与右侧抽屉

- `CAppConfigurator` 新增 `embedded=True` 模式：复用主题卡片、主色/表面色、菜单模式与
  深色模式内容，但不做固定宽度、滑入动画与自身背景绘制。
- 右侧抽屉新增 `themeMenu` 页，右侧栏最大宽度由 240 调整为 340；左右抽屉动画改为
  `minimumWidth` / `maximumWidth` 成对变化，修复只动 `minimumWidth` 时被上限夹住、
  抽屉打不开的问题。
- 标题栏与壳层预览页按钮统一为“主题配置”，共用
  `ThemeController.toggle_theme_drawer()`：收起则展开，停在主题页则收起，停在其它
  右侧页时切换到主题页。
- 标题栏整区（底板、logo、标题、分割线）恢复拖动与双击最大化；悬浮高亮不再使用
  实色块，避免盖住玻璃背景。

### 新增组件（此前 main 分支未发版）

- **数据展示族**：`CDataTable` + `CTableColumn` + `CTableModel` + `CPaginator`（列定义、过滤、排序、
  分页、多选、冻结列、分组行、行内展开详情）；`CDataView` / `CPickList` / `COrderList`；
  `CTree` / `CTreeTable`；`CTimeline`。
- **菜单族**：`CMenubar` / `CTieredMenu` / `CMegaMenu` / `CPanelMenu` / `CContextMenu` / `CTabMenu`
  共享 `MenuItem` 模型与多级子菜单；`CStepper` 步骤条。
- **文件、图表与媒体**：`CFileUpload`（拖放、后缀/大小校验、进度）、`CChart`（line/bar/pie/doughnut/
  polar/radar，QtCharts 缺失时降级）、`CImage` / `CCarousel` / `CGalleria`。
- **杂项**：`CAvatarGroup`、`CScrollTop`、`CFluid`、`CIconField`、`CInputIcon`、`CConfirmPopup`。
- **壳层**：`CAppTopbar`、`CAppMenu` / `CAppMenuItem`、`CAppConfigurator`。

### 新增示例应用

`table_preview`、`data_preview`、`menu_preview`、`media_preview`、`shell_preview`，
内置示例应用达到 10 个。

### 修复

- **栏目切换闪色**：舞台过场不再铺 `region_card_background` 实色底，页面快照保留 alpha；
  过渡期间临时隐藏页面栈，收尾先恢复栈再撤遮罩，遮罩关闭系统背景。
- **图标/文字阴影残影**：亚克力窗口不再挂整窗 `QGraphicsDropShadowEffect`，避免半透明
  窗口把内容投影透成侧栏图标周围的灰绿色残影。
- **选中菜单项右侧亮条**：选中高亮右侧内缩 4px，玻璃模式下不再绘制 `active_menu.svg`
  缺口标记，消除侧栏与内容区之间的亮竖边。
- **自绘输入/面板色差**：`CSelect`、`CInputNumber`、`CDatePicker`、`CPanel`、`CToolbar`
  等改为与 QSS 同源的玻璃底色与描边；骨架屏与滑轨颜色改取 `ColorPalette`。
- **卡片边框几何**：`#CCard_Frame` 恢复设计令牌 `border.width`，`#CRegion_Card_Frame`
  保持无描边，避免卡片与内容之间夹出异色窄环。
- **窗口外圈与标题栏**：亚克力模式去掉 10px 透明外圈，主界面与窗口边界重合；
  标题栏底板与自身补上拖动/双击处理，整条标题栏可移动窗口。
- **右侧抽屉打不开**：水平抽屉动画补齐 `maximumWidth` 动画，初始 `maximumWidth=0`
  不再夹住展开过程。
- **表格与分页闪退**：页码按钮不再在信号栈内被同步析构，改为复用 + 延迟重建；状态列回调签名对齐
  `(value, record)`；排序改用模型重置。
- **Toast 不消失**：`show_message` / `_reflow` 补启动倒计时，并加淡出兜底定时器。
- **文字截断与主题刷新**：表格/树/菜单/时间线/顶栏补省略与最小宽度；图表与树类补主题变更刷新入口。

### 重构与清理

- **相对路径**：`--apps-dir` / `--data-dir` 在 CLI 入口统一 `Path(...).resolve()`，
  应用清单不再被当成包内资源路径解析；`install-demo` / `examples --copy` 在源码树回落到仓库
  `apps/` 与 `examples/`。
- **版本号**：`customgui.__version__` 改为以 `_version.py` 为唯一来源，源码树不再显示
  site-packages 里旧 wheel 的版本；0.6.0 同时更新四套语言包中的 `sys_version`。
- **模块拆分**：`custom_ui/data/tree.py` / `data/table.py` 按角色常量、列定义、模型、委托、视图拆分；
  `guis/app_loader.py` 拆成编排、清单、命名空间、上下文、协议 v2、状态六个模块。对外导出面不变。
- **新增 `guicore.CPreviewPage`**：预览应用的页面外壳、分区卡片与语言入口收进基类，
  10 个内置示例应用的 `gui/main.py` 不再各抄一份脚手架。钩子为 `classmethod`，
  `PAGE` 写成类或实例都能被加载器正确调用（`self` 的两种含义不再需要关心）。
- **死代码**：删除 `guis/windows/loading_window/`、`appcore/tool/{device,Net,verify}.py`、
  整文件 skip 的 `tests/test_example_paradigm.py`，以及 `guicore/app_ui/dialog/` 下与
  `custom_ui/overlay/dialog.py` 重名且无人引用的 `CDialog`。
- **移除 `windows-hardware` 可选依赖**：随设备侧工具一起下线，基座运行时只依赖 PySide6 与 PyYAML。
- **CI**：新增 `.workflow/QualityGate.yml`，`main` 的 PR 与推送即跑 ruff + pytest；
  发布流水线的 ruff 由 `--select E9,F63,F7,F82` 改为项目规则集。
- **代码风格**：`ruff check src tests` 清零（原 6 条存量告警），规则集 `E/F/W/I/UP/B`。

### 破坏性变更与迁移

| 变更 | 迁移方式 |
| --- | --- |
| 标题栏主题按钮不再循环主题 | 点击改为打开右侧“主题配置”抽屉；需要旧行为请显式调用 `ThemeController.cycle_theme()` |
| `ui_SwitchTheme` 显示文案改为“主题配置” | 键名保留以兼容旧品牌包；自定义语言包若覆盖该键，请同步文案 |
| `right_column_size.maximum` 默认 240 → 340 | 品牌层若覆盖该值，请给主题配置页留出足够宽度，否则内容会被压缩 |
| 亚克力默认开启（Windows 11） | 窗口不再绘制整体外投影、也不再保留 10px 外圈；需要旧外观可设 `window.acrylic.enabled: false` |
| 主界面铺满窗口 | 不再为整窗外阴影预留边距；依赖 10px 外边距的自定义绘制需改为窗口内绘制 |

### 已知问题

- 原生亚克力仅 Windows 11 22H2+ 且系统开启「透明效果」时生效；Windows 10、Linux、macOS、
  RDP 与部分虚拟机回退为不透明主题色，属预期行为。
- 亚克力模式下没有窗口外投影；菜单、Tooltip、对话框刻意不启用亚克力，避免浮层透出
  桌面内容影响可读性。
- 低端 GPU 或远程桌面下拖动亚克力窗口可能有轻微延迟，由 DWM 合成决定，基座未做额外补偿。
- 右侧主题配置按 340px 设计；品牌层把 `right_column_size.maximum` 改小时，主题卡片会压缩。
- `ui_SwitchTheme` 键名与“主题配置”语义不一致，为兼容旧品牌包暂未改名，将在下一个
  minor 版本评估。
- 未上 PyPI；`CLineEdit` / `CPushButton` 是兼容壳；文档为手工维护，以 `__all__` 与源码为准。

## 内测版 0.5.1

### 0.5.1 已发布内容

- **配置改为逐层深合并**：`settings/` / `themes/` / `languages/` 下同名 YAML 按资源优先级
  `deep_merge`，应用品牌层只写要改的键。此前同名文件整份替换，品牌层会挤掉基座新增的必填字段，
  导致下游启动崩在 `SETTINGS_CONFIG_INVALID`。
- 新增 `iter_file_layers()`，`ConfigFile.sources` 记录参与合并的全部层。
- 迁移：无需改动。覆盖层若靠「写少一点」删除基座键，该用法本就不成立（配置没有删除语义）。

## 0.5.0

按钮与输入组件按 PrimeVue Aura 复核；抽屉从浮层改为「栏目」并新增顶/底两个方向；
修复最大化/还原时重建整窗样式表导致的卡顿。

### 破坏性变更

| 变更 | 迁移方式 |
| --- | --- |
| 移除浮层版 `CDrawer`（`customgui.guicore.CDrawer`） | 改用四向栏目：左右列由主窗口装配，顶/底列用 `CTopColumn` / `CBottomColumn`；开合用 `MainFunctions.toggle_*_column(window)` |

### 主要变更

- 新增 `CTopColumn` / `CBottomColumn`：47px 标题条 + 圆角标题胶囊 + `menus` 堆栈，与左列同构；
  尺寸区间 `top_column_size` / `bottom_column_size`，同侧开一关一。
- `CButton`：焦点框只在键盘聚焦时绘制（`set_focus_ring()` 可关）；`raised` 阴影画在盒子外；
  hover 过渡按预乘 alpha 插值，消除浅色主题「先变暗再变亮」；配色对齐 Aura 色阶。
- 输入族：hover 描边、图标着色、`CInputGroup` 外轮廓、`CInputNumber` 步进块、`CSelectButton`
  分段样式对齐参考实现；`CKnob` 新增 `value_template`。
- 下拉浮层统一到 `CPopover`（阴影、圆角、内衬、出屏翻边一处定义），`CSplitButton.popover()` 可取容器。
- 窗口：最大化/还原从重建全量 QSS 改为切换 `frameStyle` 动态属性，同步耗时从约 300ms 降到 3~20ms。
- 浮层：跟随父窗口 `Resize`/`Move` 重贴边；脏区先清透明再绘制，消除竖线叠影；浅色主题卡片改用
  `surface_app`。

## 0.4.0

围绕「应用资产跟着插件走」：根 `resource/` 不再必要、插件协议收敛到 v2、下拉框重写、四语言补齐。

### 破坏性变更

| 变更 | 之前 | 现在 |
| --- | --- | --- |
| `CComboBox` 基类 | `QComboBox` | `QWidget`（自绘，`isinstance(x, QComboBox)` 为 `False`） |
| `AppContext.icon_path` | `Path`（缺失为空 `Path`） | `Path \| None`（缺失为 `None`） |
| `AppContext.language` | 构造时快照 | property，每次读最新值 |
| 清单校验 | 无 | `app_name` 必须等于目录名；`protocol` 只能 `1` / `2`，违规抛 `AppPluginError` |
| `register_app_provider` | 单槽覆盖 | 列表 + 深度合并 |

### 主要变更

- **插件协议 v2**：`AppPlugin` / `AppPage`，声明式页面 `build(ctx, window)`，基座负责
  `setObjectName` 与入栈；`on_load(ctx)` 在页面构建前调用。清单 `protocol: 2` 启用。
- **应用品牌层** `<app>/brand/`：`resource_roots()` 自动扫描，应用自带主题/语言/图标零配置生效。
- **四语言**：`zh_cn` / `zh_tw` / `en_us` / `ja_jp` 逐键对齐，`LANGUAGE_OPTIONS` 改为惰性发现。
- 新增 `appcore.tool.storage`（原子写）、`guicore.fonts`（CJK 字体）、`guicore.callbacks`（回调守卫）、
  `guicore.task`（后台任务）。
- `CComboBox` 弹出层改自绘，修复黑角、被滚动区裁剪、滚轮误改选中项。

## 0.3.0

**结构性重构**：目录、包名、导入路径全变。

### 破坏性变更

| 变更 | 之前 | 现在 |
| --- | --- | --- |
| 包布局 | 根目录四个顶层包 `AppCore/` `GuiCore/` `Guis/` `customgui/` | 单包 `src/customgui/{appcore,guicore,guis}` |
| 子包命名 | `SYS` `APP` `Tool` `CustomUI` `WindowDefineUI` `AppDefineUI` | `sysx` `app` `tool` `custom_ui` `window` `app_ui` |
| 资源位置 | `customgui/resource/` | `src/customgui/_resources/` |
| 应用目录 | `Apps/` | `apps/` |
| 示例入口 | `main.py` | `examples/hello_world/main.py` |
| 应用命名空间 | `customgui_apps.<name>` | `_customgui_apps.<name>`（私有） |
| 左右列实现 | `guis/columns/` | `guicore/window/{left,right}_column/`（对外名字不变） |

### 迁移

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

### 同版本新增

- `customgui.window` 门面、`customgui.configure()`、`customgui` 命令行（`run` / `install-demo` /
  `examples` / `doctor`）、`AppHandle`、`py.typed`。
- 内置示例与最小工程随 wheel 分发（`force-include`）。

## 历史版本摘要

| 版本 | 主题 |
| --- | --- |
| `0.2.4` | PyCL2 基座能力回流：页面懒加载、主题强调色覆盖、标题栏信号 sender 修复、语言订阅清理 |
| `0.2.3` 及更早 | 早期组件与窗口骨架迭代；细节见 git 历史 |

> 更早的逐条修复记录已从本文件移除，需要追溯时使用 `git log -- CHANGELOG.md`。
