# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。`0.x` 阶段 minor 版本可能含
破坏性变更，均在下方显式列出。

## 未发布

按钮组件按 PrimeVue Aura（`sakai-vue` 的 Button 页）做了一轮全盘复核，修掉渲染偏差。

### 修复

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

### 变更

- `CButton` 新增 `icon_size` / `focus_ring` 参数；`set_divider`（分体按钮的伪分隔线）移除。
- `CSplitButton.items` 支持 `None` 作为分隔线，并新增 `set_items` / `items` / `menu()`；
  `guicore.custom_ui.paint_utils` 新增 `shadow_layers` / `draw_shadow` / `SHADOW_MARGINS`（按钮与浮层共用）。
- 按钮预览页：分组标题对齐 Sakai 的 `text-xl`，自定义内容用 24px 图标，分体按钮菜单补齐
  分隔线与 `pi-times` 图标。

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
