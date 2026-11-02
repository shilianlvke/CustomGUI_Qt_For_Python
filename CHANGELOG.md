# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。`0.x` 阶段 minor 版本可能含
破坏性变更，均在下方显式列出。

## 0.5.1

### 修复

#### 配置：同名文件逐层合并，不再整份替换

- **覆盖层的配置文件改为「深合并」而不是「整份替换」**：`settings/` / `themes/` /
  `languages/` 下同名 YAML 现在按资源优先级**逐层 `deep_merge`**（基座打底 → 应用
  品牌层覆盖），应用只需写要改的键。此前 `iter_files()` 同名只保留最高优先级那份，
  品牌层 `window.yaml` 会把基座那份整份挤掉——基座 0.5.0 给 `AppSettings` 加了必填
  字段 `top_column_size` / `bottom_column_size` 后，下游 py-cl2 启动即崩在
  `SETTINGS_CONFIG_INVALID`（报「AppSettings 缺少关键字段」），而错误信息完全看不出
  是覆盖层造成的。
- **新增 `customgui.appcore.sysx.config.paths.iter_file_layers()`**：返回
  `{相对路径: (低优先级, ..., 最高优先级)}`，供配置装载逐层合并。
  `iter_files()` 语义不变（同名只要最高优先级那份），仍是发现类调用与存在性判断的入口。
- **`ConfigFile` 新增 `sources`**：记录参与合并的全部层（低 → 高）；`path` 仍指向
  最高优先级那层，也就是「想改配置时该编辑的文件」。

迁移：无需改动。覆盖层若是**故意**用「写少一点」来删掉基座键，现在会被基座键补回来——
这种用法本来就不成立（配置没有「删除」语义）。

## 0.5.0

按钮组件按 PrimeVue Aura（`sakai-vue` 的 Button 页）做了一轮全盘复核，修掉渲染偏差；
输入组件按同一套手法对照 `InputDoc` 复核了一遍；抽屉从浮层改为「栏目」组件并新增
顶/底两个方向，同时修掉最大化/还原时整窗重建样式表导致的卡顿。

### 破坏性变更

| 变更 | 迁移方式 |
| --- | --- |
| 移除浮层版 `CDrawer`（`customgui.guicore.CDrawer`） | 改用四向栏目：左/右列由主窗口装配，顶/底列用 `CTopColumn` / `CBottomColumn`；开合走 `MainFunctions.toggle_*_column(window)` |

### 新增

#### 四向抽屉（栏目：`CTopColumn` / `CBottomColumn`）

- **抽屉从浮层改为「栏目」**：移除浮层版 `CDrawer`（见破坏性变更）。左列
  `CLeftColumn` 即左侧抽屉、右列 `Ui_RightColumn` 即右侧抽屉，用法完全不变；
  参照两者的结构与交互新增：
  - `CTopColumn`（`guicore/window/top_column/`）：停靠在标题栏下方、内容区上方；
  - `CBottomColumn`（`guicore/window/bottom_column/`）：停靠在内容区下方、版权栏上方。
- 顶/底列与左列同构：47px 标题条 + 圆角标题胶囊（`#CTopColumnTitle_Frame` /
  `#CBottomColumnTitle_Frame`）+ 30×30 图标位 + 30×30 关闭按钮，复用 `PyIcon` /
  `PyLeftButton`；内容区是 uic 生成的 `Ui_TopColumn` / `Ui_BottomColumn`
  （`menus` 堆栈 + 透明滚动区），由配套的 `top_column.ui` / `bottom_column.ui` 编译。
- 开合与左/右列同一套规则：`MainFunctions.toggle_top_column()` /
  `toggle_bottom_column()` 动画 `minimumHeight`（`start_box_animation_vertical`），
  尺寸区间 `top_column_size` / `bottom_column_size`（默认 0~240），同侧开一关一；
  `top_column_is_visible` / `bottom_column_is_visible` / `set_top_column_menu` /
  `set_bottom_column_menu` 与左列的可见性与换页助手一一对应。
- 关闭按钮 `btn_close_top_column` / `btn_close_bottom_column` 沿 `clicked/released`
  汇入主窗口按钮总线，`MainWindowButtonUseCase.ACTION_MAP` 与 `ColumnController`
  统一路由，和 `btn_close_left_column` 同一条链路。
- 预览页抽屉卡改为四个方向的开合演示（左侧抽屉 / 右侧抽屉 / 顶部抽屉 / 底部抽屉）。

### 修复

#### 输入组件

- **输入框描边与文字**：hover 描边原本取 `surface_interactive_hover`，深色主题下比常态
  边框**更暗**；改为「常态描边 → 正文色」的 35% 混合，深浅主题都更醒目。输入文字改用
  `text_active`，invalid 描边两种主题统一为 Aura 的 `red.400` `#f87171`，且 QSS 与
  自绘组件（下拉框 / 日期框 / 输入框组）取同一份颜色。
- **输入框图标着色**：图标 SVG 自带写死的强调蓝，直接 `QIcon(svg)` 会永远那个颜色；
  改为按 `form.field.icon.color` 栅格化着色，主题切换时重新着色。
- **输入框组（`CInputGroup`）**：addon 原来只在**共享边**画线、外侧反而没有边，看上去
  像浮在控件外面的图标。现按 Aura 规则只画外轮廓边（first-child 补左、last-child 补右、
  紧跟另一个 addon 时补左），共享边交给邻居的边框，addon 底色与输入框同色。
- **数字输入步进块（`CInputNumber`）**：底色几乎不可见、左边缘重复描边、箭头是小三角；
  改为底色跟随输入框、左边缘不描边、中间分隔线 + chevron 箭头 + 上/下半区 hover 高亮，
  并补上 `set_corners` 以便在输入框组里合并圆角。
- **分段单选（`CSelectButton`）**：选中段原本内缩成一颗独立圆角按钮；改为段铺满整格、
  共享外框、内部 1px 分隔线（挨着选中段的那条取强调色）。
- **`CKnob`**：新增 `value_template`（对齐 PrimeVue 的 `valueTemplate`）。
- **输入预览页**：卡片划分与参考页对齐（6 张卡片、一张卡片多个小标题，Rating / ColorPicker
  并排），去掉参考页没有的「尺寸」分组，ToggleSwitch 不再带标签，ToggleButton 固定 10em，
  分组标题与按钮页统一用 `title_size`。

#### 下拉浮层（`CDropdownField` 一族 + 分体按钮菜单）

- **浮层右下角「透明直角」**：`CPopover` 是半透明独立窗口，圆角只由 `QPainterPath` 决定、
  圆角外 alpha=0，且**没有阴影**——叠在比它浅的卡片/页面上时，那一角就是一块见底的缺口。
  现在按 Aura 的 `overlay.navigation.shadow` 在本体外圈画阴影（复用 `paint_utils.draw_shadow`），
  并加 `Qt.NoDropShadowWindowHint` 关掉系统矩形投影。
- **内容内衬**：原来布局内衬 4px 小于圆角半径 8px，子控件（列表悬停行、日历、色板）可能画进
  圆角把它削平；改为「阴影边距 + `POPOVER_INSET`(6px)」，内容不再进入圆角区。
- **统一两套实现**：分体按钮的弹出菜单原本是另一个 `Qt.Popup` 窗口、自己画阴影/圆角；
  现拆成「`_SplitMenu` 只画菜单行 + `CPopover` 负责浮层外观」，与 `CSelect` / `CMultiSelect` /
  `CAutoComplete` / `CTreeSelect` / `CDatePicker` / `CColorPicker` 共用同一个容器，
  圆角、阴影、内衬、出屏翻边只有一处定义。`CSplitButton.menu()` 返回菜单内容，
  新增 `CSplitButton.popover()` 返回浮层容器。

#### 按钮组件

- **`CButton` 焦点框**：只在键盘聚焦（`Tab` / `Shift+Tab`）时绘制，鼠标点击不再留框，
  等效 CSS 的 `:focus-visible`；需要整块关掉时用 `set_focus_ring(False)`（组件级，与全局 QSS 无关）。
- **`CButton.raised` 阴影**：此前阴影被控件矩形裁掉，视觉上等于没有。现在为阴影预留
  透明边距、真正画在按钮盒子之外，且四种 variant 都生效——Sakai 的 Rounded Text 就是
  `text + raised + rounded`。
- **`CSplitButton` 右侧展开按钮报错**：`from .menu import CMenu` 写成同级包，应为 `..menu`。
  同时把弹出内容换成按 Aura `.p-menu` 规格自绘的 `_SplitMenu`（6px 圆角卡片 + 描边 + 阴影 +
  4px 内衬 + 36px 圆角菜单项 + 悬停高亮 + 着色图标 + 分隔线 + 200px 最小宽度 + 出屏翻边），
  `QMenu` 的原生渲染做不出这套排版。
- **hover 时「闪一下」**：两个根因都修了。
  1. 过渡起点原本取「上一个稳定状态」，鼠标快速划过时过渡被打断会先跳回原色再走一遍；
     现在起点取**上一次实际画出来的颜色**，打断后能平滑反向。
  2. 颜色插值按 RGBA 逐分量做，`全透明(0,0,0,0) → 不透明浅色` 的中途会经过半透明灰，
     叠到卡片上就是「先变暗再变亮」——浅色主题（bright / eye）下尤其明显。改为**预乘 alpha**
     插值后，中间帧只剩「目标色 + 部分不透明度」，色相不再跑偏。
  受影响的是常态底色全透明的 text / outlined（含圆角变体）四类按钮，solid 一直是正确的。
- **按钮组 / 分体按钮的 1px 白缝**：底色改为铺满整个控件矩形，只有描边内缩 0.5px。
- **配色对齐 Aura 色阶**：outlined 描边改取 200 档（深色主题 700 档）；text / outlined 的
  hover/active 底色改取 50/100 档（深色主题按 4%/16% 叠加）；secondary / contrast / plain
  统一走 surface 色阶；主色实心按钮的文字改为白字（此前按 HSL 亮度判成近黑，与其它语义色不一致）。
- **loading 排版**：spinner 占前置图标位、文案保留，转速改为 Aura 的 2s/圈；禁用态透明度改为 0.6。

#### 窗口（最大化/还原卡顿）

- **点击最大化卡一下、还原再卡一下**：`maximize_restore()` 调 `set_stylesheet()`
  重建整张全局样式表并 `setStyleSheet` 到整个窗口，实测一次切换触发 **2780 次
  StyleChange、同步阻塞 280~340ms**（`Styles()` 自身只占 ~3ms，其余全是整棵控件树
  重新 polish + 重新布局）。
  改为 `#CWindow_Frame[frameStyle="flat"]` 动态属性：切换时只 `unpolish/polish`
  框架本身，同步耗时降到 **3~20ms（约 20~90 倍）**，StyleChange 归零，
  LayoutRequest 从 ~139 降到 ~8。
- 最大化时关闭 `QGraphicsDropShadowEffect`：满屏时阴影不可见，却会让整窗走离屏合成。
- 最大化状态由模块级全局改为 `CTitleBar` 实例属性，多窗口不再互相串状态；
  按钮图标与提示（新增 `language.UI.ui_Restore`）随状态同步更新。

#### 浮层（对话框 / 浮层面板）

- **抽屉开着最大化/还原后停在旧位置**：浮层是独立顶层窗口，Qt 不会带着它一起动。
+  `_OverlayBase` 现在监听父窗口的 `Resize`/`Move`（延到下一轮事件循环，等内容区
+  布局完成再取锚点尺寸）重新贴边，滑入动画途中的终点也会改到新位置。
- **卡片边缘出现一串越来越密的竖线**：透明窗口不做背景擦除，遮罩/投影在局部重绘时
+  反复叠 alpha（滑入、最大化时最明显）。`paintEvent` 先把脏区清成透明再绘制，
+  卡片动画期间逐帧刷新整层遮罩。
- **浅色主题下抽屉/对话框是一张纯白卡片**：`COverlayCard` 底色改为设计令牌的
+  `surface_app`（深色主题数值不变），`eye`/`bright` 下与板面同色。

### 变更

- **区域背景卡片（微前端基座的视觉层次）**：主内容区（插件页面容器）与四向抽屉
  （左/右/顶/底列）统一挂 `#CRegion_Card_Frame` 区域卡片——底色取 `surface_app` 与
  `surface_panel` 的中间调（区别于窗口底色，也不与页面里的 `surface_card` 撞色）、
  描边沿用窗口框的 `border.width` + `surface_interactive_pressed`、圆角取
  `radius.window`，五个区域一套规则，四套主题自动跟随。内容卡片与右列卡片之间
  留出 `right_content_space` 间距，页面内容从卡片描边内缩 5px；最小窗口尺寸
  （960×540）下开合抽屉均无遮挡冲突。
- `CButton` 新增 `icon_size` / `focus_ring` 参数；`set_divider`（分体按钮的伪分隔线）移除。
- `CSplitButton.items` 支持 `None` 作为分隔线，并新增 `set_items` / `items` / `menu()`；
  `guicore.custom_ui.paint_utils` 新增 `shadow_layers` / `draw_shadow` / `SHADOW_MARGINS`（按钮与浮层共用）。
- 按钮预览页：分组标题对齐 Sakai 的 `text-xl`，自定义内容用 24px 图标，分体按钮菜单补齐
  分隔线与 `pi-times` 图标。
- `CWindow.set_stylesheet()` 不再重建样式表：`(0, 0)` 走 `frameStyle="flat"` 动态属性，
  主题重建仍由 `apply_style()` 负责（主窗口控制器已订阅主题变更）。
- `CCloseButton` 新增 `radius` 参数：传值时为圆角方形（抽屉/标题栏用），不传保持圆形。
- 新增语言键 `language.UI.ui_Restore`（还原）。

## 0.4.0

本轮围绕「应用资产跟着插件走 + 反哺 PyCL2」：根 `resource/` 不再必要、插件协议
收敛到 v2、下拉框重写、四语言补齐。

### 破坏性变更

| 变更 | 之前 | 现在 |
| --- | --- | --- |
| `CComboBox` 基类 | `QComboBox` | `QWidget`（自绘，`isinstance(x, QComboBox)` 变 `False`） |
| `AppContext.icon_path` | `Path`（缺失时为空 `Path`） | `Path \| None`（缺失为 `None`） |
| `AppContext.language` | 普通字段（构造时快照） | property（每次读最新值） |
| 清单校验 | 无 | `app_name` 必须等于目录名、`protocol` 只能 `1`/`2`，违规抛 `AppPluginError` |
| `register_app_provider` | 单槽（后注册覆盖先注册） | 列表 + 深度合并（后注册覆盖同名键） |

### 新增

- **插件协议 v2**（`customgui.appcore.AppPlugin` / `AppPage`）：声明式页面
  `build(ctx, window)`，**基座负责** `setObjectName` 与 `addWidget`，应用不再手工
  入栈。清单 `protocol: 2` 启用；`on_load(ctx)` 钩子在页面构建前调用。
  入口识别三种写法：`PLUGIN` 实例 / `PLUGIN` 类 / 模块内唯一子类（多个时须显式指定）。
- **应用品牌覆盖层 `<app>/brand`**：`resource_roots()` 自动扫描每个应用的
  `brand/customui/`，应用自带主题/语言/图标**零配置**纳入解析链。根 `resource/` 不再必要。
- **`LANGUAGE_OPTIONS` 惰性化**：按当前资源根解析并缓存，`configure()` 后自动失效；
  应用后叠加的语言（如日语/繁体）无需环境变量抢跑也能被发现。
- **四语言 87 键**：补齐 `zh_tw` / `ja_jp`，与 `zh_cn` / `en_us` 逐键对齐。
- **`appcore.tool.storage`**：原子化 JSON/文本读写（`read_json` / `write_json` /
  `read_text` / `write_text`，`fsync` + `os.replace` + `.bak` 回退）。
- **`guicore.fonts`**：`install_fonts` / `install_system_fonts`，解决 offscreen /
  远程会话下 CJK 字体豆腐块。
- **`guicore.callbacks`**：`is_deleted_qt_error` / `safe_callback` / `ui_callback` /
  `single_shot`，页面销毁后仍被信号回调不再刷屏。
- **`guicore.task`**：`ProgressUpdate` / `TaskWorker` / `WorkerSignals` / `run_task` /
  `active_tasks`，带取消协议与宿主生命周期管理。
- **`AppContext` 升级**：`core_dir`（清单 `core`）、`module_name`、`import_module()`、
  `brand()`；`AppHandle.plugin` 暴露 v2 插件实例。

### 修复

- **`CComboBox` 原生弹出层黑角**：弹出层改为顶层窗口的透明子控件 + `QPainter` 自绘
  圆角底板，深色主题不再露角、不被 `QScrollArea` 裁剪；`wheelEvent` 一律 `ignore()`，
  滚动页面不再误改选中项；尺寸改为 `Expanding/Fixed` 可伸展，显示条数可配。
- **`_NAMESPACE_ROOTS` key 不一致**：原来用目录名登记、用 `app_name` 建模块名，两者
  不一致时应用内跨目录导入静默失效；统一按模块名，清单校验兜底。
- **语言切换幂等判断**：由「比较语言名」改为「比较内容签名」，运行期追加/修改语言
  文件也能重新装载。

### 测试

`270 passed, 5 skipped` → **`376 passed, 5 skipped`**（净增 106 条，覆盖下拉框行为、
资源布局解析、语言覆盖、协议 v2、命名空间 Finder、存储、回调守卫、后台任务）。

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
