# 更新日志

项目遵循[语义化版本](https://semver.org/lang/zh-CN/)：major 版本允许破坏性变更并显式列出；
minor 与 patch 保持向后兼容。

当前版本：`2.1.4`（见 `src/sllkgui/_version.py`），对应 tag `base-v2.1.4`。

---

## 2.1.4（2026-11-12）

- 修复 `window.yaml` 的 `minimum_size` 只存在于 Schema、从未作用到窗口的问题：
  启动时显式 `setMinimumSize`，并把当前窗口放大到该尺寸（屏幕更小时以屏幕
  可用区域为上限）。
- `user.yaml` 没有窗口尺寸时回落到 `window.yaml` 的 `startup_size`。
- 关闭窗口写入 `user.yaml` 时不再保存小于 `minimum_size` 的尺寸。

## 2.1.3（2026-11-12）

- 插件管理恢复「模式导轨 + 工作区」布局（已安装 / 发现 / 源），保留顶部指标
  与已安装详情面板。
- 发现改为搜索框 + 两列结果卡片，每张卡片直接安装；来源改为紧凑行，支持
  逐行刷新/移除；两处均不再使用 `CPickList` / `COrderList`。
- 插件管理按钮保持在下方、位于「软件信息」之上。

## 2.1.2（2026-11-12）

- 菜单分区：插件管理（核心插件）移到下方、位于「软件信息」之上；普通插件
  Surface 仍在顶部轨道。
- 插件管理页重写为编辑式单页控制台：不再使用 `CPickList` / `COrderList`，
  改为「01 已安装 → 02 发现 → 03 来源」三段式布局；已安装用整行卡片把
  版本、状态、来源、权限与操作同屏展示，发现用两列结果卡片直接安装，
  来源用紧凑行管理。

## 2.1.1（2026-11-12）

- 修正左菜单分区：插件 Surface 按钮注册到顶部轨道，底部只保留「软件信息」。
- `core_store` 合并为单页插件管理工作台（`store` Surface）：左侧模式导轨
  （已安装 / 发现 / 源）+ 顶部指标，已安装用插件卡片与详情清单，发现用
  `CPickList` 挑选安装队列，源用 `COrderList` 管理优先级；删除原三个 Surface。

## 2.1.0（2026-11-12）

- 新增基座托盘能力：全应用唯一 `QSystemTrayIcon`，插件通过 `ctx.tray`
  注册动作/通知（新权限 `tray`），不再自建托盘；托盘可见时关闭主窗口只隐藏，
  「显示主窗口」「退出」由基座提供。方案见 `docs/TRAY.md`。
- 插件清单新增 `python_dependencies`（PEP 508）：加载器在导入插件前检查缺失，
  按用户选择用 `uv pip install` 安装到当前解释器；失败隔离并记录
  `PYTHON_DEPENDENCY_MISSING` / `PYTHON_DEPENDENCY_INSTALL_FAILED`。
- `sllkgui run` 启动时检测 uv / Git，缺失时允许用户选择自动安装或手动安装；
  uv 使用官方脚本（`irm https://astral.sh/uv/install.ps1 | iex`）安装，
  Windows 上 Git 优先用 winget；仅影响源安装/刷新，不阻塞启动。
- 新增镜像源配置：`run --index-url`、`SLLKGUI_PIP_INDEX_URL`、
  `configure(pip_index_url=...)`；`run --no-install-deps` 只检查不安装。
- `doctor` / `plugin doctor` 输出 `tools` 与生效镜像源。

## 2.0.2（2026-11-12）

- 修复点击 Gallery 左菜单时报 `TypeError: unhashable type: 'LanguageHandler'`：
  `get_page_routes()` 与 `SurfaceRecord.display_title()` 统一把传入的
  `Language` 单例归一为语言代码。

## 2.0.1（2026-11-12）

- 修复 Windows 换行转换导致 `manifest_sha256` 与源条目不一致：清单哈希统一
  按 LF 计算，Linux/macOS/Windows 校验结果一致。

## 2.0.0（2026-11-12）

### 破坏性变更

- 删除 App 协议 v1/v2：`AppPlugin` / `AppPage` / `app_*` 加载器、`apps/`、
  `config.yml`、`plugins.yml`、`SLLKGUI_APPS_DIR` 全部移除，不保留兼容层。
- 基座版本升到 `2.0.0`，python 依赖新增 `packaging`。
- `sllkgui run` 不再接受 `--apps-dir`，改用 `--gallery-dir` / `--plugin-dir`。

### Gallery 插件运行时

- 新增 `sllkgui.gallery`：清单校验、源索引、Git 安装、SemVer 依赖解析、
  状态持久化、加载器、Surface 注册表、Gallery 外壳与 lint/scaffold。
- 新增公开 API `sllkgui.plugin`：`Plugin` / `GalleryContext` / `Permission` /
  `PLUGIN_API_VERSION`；上下文提供 `log` / `logger` / `event` / `timing` /
  `report_error` / `text` / `data_dir` / `resource` / `open_surface`。
- 新增命令：`gallery`、`source`、`plugin`、`scaffold`；`doctor` 支持 `--json`。
- 插件规范：日志/遥测必须全量接入基座；`sllkgui plugin lint` 与源仓库 CI 检查。

### 内置插件

- `showcase/core_preview`：原 10 个组件预览 App 合并为一个插件、10 个 Surface，
  仅 `sllkgui gallery` 加载。
- `core_plugins/core_store`：已安装插件、搜索安装、源管理三个 Surface，
  `sllkgui run` 始终加载（含 `--safe-mode`）。

### 窗口与语言

- 左菜单与页面路由改由 `GalleryRegistry` 提供，页面首次导航时懒构建。
- 语言切换后通知插件的 `on_locale_changed`；主题订阅支持正确退订。
- 设置页页面数改为 Gallery Surface 数量。

---

## 1.0.5（2026-11-11）

### 左菜单

- 页面按钮与设置入口（底部齿轮）的激活态统一用主题强调色：此前齿轮走
  「tab」配色（灰白强调条），在亚克力底上几乎与悬停态同色，看起来像没激活。
  现在两者强调条与图标颜色完全一致，设置抽屉打开时齿轮与当前页面按钮同时
  高亮，且视觉上区分得出来。

---

## 1.0.4（2026-11-11）

### 左侧抽屉

- 关闭按钮改用与右侧外观抽屉同款的 `CCloseButton`（28×28、圆角 6、静止无
  底色、悬停才出现淡底），不再常亮一块方块。
- 设置页按「设置卡片」重排：每页一张圆角卡片，卡片内是弱化键 + 主色值的
  信息行；移除 `SLLKGUI` eyebrow 与页内重复的页面大标题，层级交给分段导航。
- 目录改为按实际宽度中部省略 + tooltip 全文，不再固定像素截断。
- 宿主 `add_section()` 追加的区块自动套同一张卡片，py-rm 等应用无需改调用。

### 左菜单

- 顶部页面按钮与底部设置入口改为**两段各自保留一个激活项**：打开设置抽屉
  时底部齿轮高亮，顶部当前页面按钮不再被清掉。
- `deselect_all_tab()` 支持按分段清除（`top` / `bottom`），未找到目标的
  `select_only_one_tab()` 不再误清另一分段。

### 浮层抽屉

- 左 / 上 / 下三个抽屉框在 `drawer_mode=overlay` 时改用与浮层左菜单同一套
  玻璃表面（`glass.overlay_panel`，最小不透明度 0.90）并加 1px 描边；
  右侧外观面板自绘同步改用同一组颜色，四个浮层抽屉不再出现「有的全透明、
  有的实色」。

---

## 1.0.3（2026-11-11）

### 发布流程

- `twine check` 只校验本次构建出的 `sllkgui-<version>-*.whl`，不再连带
  `dist/` 里的历史 wheel。

## 1.0.2（2026-11-11）

### 发布流程

- 新增 `scripts/release_base.py`：一条命令完成补丁版本发布
  （bump patch → ruff + mypy + pytest 70% + wheel + twine → 提交 → 打
  `base-vX.Y.Z` tag → 推送）。任一步失败即退出，不会留下半发布状态。
- `twine check` 改为在 Python 侧展开 `dist/*.whl`，Windows 下不再因 shell
  不展开通配符而失败。

## 1.0.1（2026-11-11）

### 左侧抽屉

- 左抽屉标题条新增副标题「软件与环境」，与右侧外观抽屉的标题层级保持一致；
  语言切换时标题与副标题同步刷新。
- 设置页改为「概览 / 运行环境 / 目录」三个单屏子页，顶部分段导航切换，
  移除单页堆叠与滚动。
- 宿主区块按页追加：概览页放启动行为，目录页放目录入口；外观配置仍走标题栏
  独立入口，不在设置页重复。
- `set_left_column_menu` 改用 `set_title`，保留语言键，修复打开抽屉后标题
  回退成 `language.UI.ui_Settings` 的问题。

### 外观抽屉

- 右侧外观配置改为浮层覆盖内容区，不再占用布局宽度，打开时不会压缩主页面
  产生横向滚动。
- 抽屉内部由单一滚动长页改为「主题 / 材质 / 背景 / 界面」四个单屏子页，
  顶部分段导航切换；移除内部滚动区。
- 主题卡片背景改用设计令牌表面色，明亮主题下不再出现暗色卡片。
- 保留主题、语言、菜单模式、材质滑块与背景手风琴的既有信号与持久化行为；
  关闭按钮与标题栏外观按钮的选中态保持同步。

### 设置入口

- 「软件信息」按钮改为设置的唯一入口：点击打开左侧抽屉，抽屉内容为「概览 / 目录」
  两个单屏子页；再次点击同一入口收起抽屉，停在其它左列页时只切换到设置页。
- 移除左抽屉 `menu_2` 的占位滚动区，改为 `CSettingsPanel`；`CLeftColumn.settings_page`
  暴露给宿主应用追加设置区块。
- 外观配置仍由标题栏色盘独立入口负责，设置页不重复放置主题/语言控件。
- 四语言新增设置页文案；补充 `btn_info` 开合与切换回归测试。

### 内存优化

- `install_system_fonts()` 改为按字体族按需注册：系统已能发现
  Microsoft YaHei / Segoe UI 时不再重复加载字体文件。旧实现无条件注册
  5 个 Windows 字体，实测常驻内存多占约 270 MB。
- 移除全局 QSS 中 `QFrame { font: ... }` 兜底规则：Qt 会为被样式化的
  QFrame/QLabel 建立字体解析缓存，首次应用样式表时多占约 65 MB。
- 最近背景缩略图改用 `QImageReader` 按 2 倍目标尺寸解码，不再为 64×40
  的缩略图完整加载 4K 原图；5 张最近背景由上百 MB 降到约 5 MB。
- 外观配置面板改为首次打开抽屉时惰性创建（`CAppConfigurator` 含 4 个
  单屏子页与大量自绘控件）；启动不再为未打开的面板构建控件树。
  自定义宿主仍可提前注入 `ui.theme_config`，控制器会自动接线。

### 四向抽屉模式

- 新增全局 `drawer_mode`（`static` / `overlay`），统一控制左 / 右 / 上 / 下四个
  抽屉：`static` 在布局内占位并挤压内容区，`overlay` 浮在内容区之上且内容区
  尺寸不变。`menu_mode` 仍只控制左侧图标菜单，两者互不影响。
- 外观配置「界面」页新增「抽屉模式」分段控件；切换后立即应用并写入
  `user.yaml`（schema 升级到 v4，v3 → v4 只记录跃迁、不注入默认值）。
- 运行期切换模式会保留已展开的抽屉：左侧设置、外观面板等不会因换容器而消失。
- 右侧外观面板支持运行期在「嵌入右列」与「浮层滑入」之间切换；
  `CAppConfigurator.set_embedded()` / `is_embedded()` 对外开放。
- 顶 / 底抽屉在 Overlay 下仍保持「同一主轴只开一个」的既有约定。
- 新增 2 种模式 × 4 个抽屉的回归测试，覆盖展开、收起、内容区尺寸不变与
  模式切换后的状态恢复。

---

## 1.0.0（2026-11-05）

### 项目更名

- 分发名、顶层包名、模块导入名与命令行统一由 `customgui` 改为 `sllkgui`
  （PyPI 上的 `customgui` 已被无关项目占用）。
- 环境变量统一改为 `SLLKGUI_*`；资源命名空间由 `customui/` 改为 `sllkgui/`；
  插件品牌覆盖层改为 `<app>/brand/sllkgui/`。
- 应用私有命名空间由 `_customgui_apps` 改为 `_sllkgui_apps`；日志文件改为
  `logs/sllkgui.log`。旧安装需重新执行 `uv sync` / `pip install -e .`。

### 个性化背景图

- 外观配置新增「个性化设置背景」手风琴：标题行常驻（图片图标、说明、类型下拉、
  展开/收起箭头），展开后提供最近图片缩略图、浏览照片、清除背景与适应模式选择。
- 背景图支持填充 / 适应 / 拉伸 / 平铺 / 居中五种模式，随窗口尺寸缓存缩放结果，
  最大化/还原时按 `frameStyle` 自动切换直角或圆角裁切。
- 背景图激活时侧栏、面板、卡片、输入框等表面自动转为半透明，并保留可读性下限；
  清除后恢复主题纯色，无需重启。
- 新增用户配置字段 `background_image` / `background_fit` / `background_recent`
  （schema v3），启动时由 `SetupMainWindow.restore_ui_state` 自动恢复。
- 四语言新增背景设置文案；补充手风琴、持久化、窗口绘制与启动恢复测试。

### Windows Fluent Design 全量视觉重构

- 设计令牌统一为 Fluent 规范：字体 `Segoe UI Variable`，标题 / 副标题 / 正文
  15 / 11 / 10pt；控件圆角 4px，窗口 / 卡片 / 浮层 8px；控件高度 28 / 32 / 40px。
- 按钮语义色不再写死 PrimeVue Aura / Tailwind 色阶，改为从四套主题的
  强调色与 `custom_green` / `custom_yellow` / `custom_red` 实时解析；语义文本按
  实际对比度自动选择黑/白。
- 按钮默认平面化，`raised` 仅作可选浮起；禁用态改为中性底 + 弱化文字，
  不再把语义色整体降透明度；普通按钮使用箭头光标，仅链接型按钮使用小手。
- 输入框、下拉框、日期、数字框统一为 Fluent 控件描边（正文色 26%–42%），
  聚焦态改为 2px 强调色底边；三档高度收缩为 28 / 32 / 40px。
- 复选框 / 单选 / 开关 / 滑块补齐 Fluent 焦点环、禁用透明度与手柄内圈；
  开关尺寸 40×20、滑块手柄 20px；进度条默认高度 4px。
- 表格改为 Fluent 列表式：表头随卡片底色（深色主题不再出现亮色表头）、
  去掉斑马纹、选中态为强调色低透明度、表头字体 600。
- 左侧导航选中态改为“中性底 + 左侧 3px 强调条”，移除 Sakai 右侧缺口标记；
  标签式菜单激活项只保留下划线，移除灰色胶囊；菜单项圆角 4px、行高 36px。
- 提示气泡改为 8px 圆角 + 中性描边 + 短距离阴影，移除彩色强调边。
- Toast / 内联消息 / 骨架屏 / 图表 / 媒体 / 上传 / 浮层等统一使用主题色、
  8px 圆角与 Fluent 高度阴影，移除 Aura 硬编码灰阶与 PrimeVue 命名。
- 新增 `tests/test_fluent_design.py` 锁定几何令牌、语义色与四主题一致性；
  `docs/ARCHITECTURE.md` 增补 Fluent 设计规范。

### 外观配置

- 新增“材质与通透度”分区：窗口透明度与亚克力质感强度两枚横向滑块，拖动实时
  生效并写入用户配置。
- 修复标题栏外观按钮选中态使用实色亮白底、与整体风格不协调的问题，改为强调色
  低透明度叠层。
- 修复亚克力质感强度拉满时主窗口底色 Alpha 归零、Windows 分层窗口出现鼠标
  穿透的问题；主窗口底色保留最小不透明度。

### 视觉清查

- 浮层菜单、下拉框内容与展开弹层统一使用「菜单级」高不透明度玻璃底，并随
  亚克力质感强度变化；`CComboBox` 弹层不再沿用输入框 30% 透明底。
- 修复亮色主题菜单悬停行取纯白、几乎不可见的问题；悬停底色改为主题的悬浮层色。
- 浅色主题（bright / eye）的中性色阶改由调色板派生，护眼主题不再混入灰白色块。
- 强调色前景（步进器、列表选中项、日期选择、复选框、开关滑块）按实际亮度
  自动选择黑/白，修复 dracula 浅粉强调色上的低对比度。
- 对话框卡片、Toast、时间线卡片、上传拖放区、回顶按钮等大块/浮起表面补齐
  亚克力强度适配，并保留可读性下限。

- 语言切换与主题配置合并为统一的“外观配置”模块，标题栏只保留一个色盘图标入口，
  移除独立的语言按钮；原 `btn_themes` 对象名保留以兼容既有接线。
- 语言改为在抽屉内直接选择目标语言，不再循环轮替；切换后抽屉标题、分区与
  菜单模式选项随语言同步刷新。
- 抽屉内部重排为“主题（含深色模式）/ 语言 / 菜单模式”三个分区，移除不可交互的
  “主色 / 表面色”示意色板与“仅作示意”说明。
- 清理壳层预览、菜单预览中的操作结果与点击回调状态文案，界面只保留面向用户的
  指引。

### 配置持久化

- 新增 `<data_root>/settings/user.yaml` 用户配置覆盖层：主题、语言、菜单模式在
  运行时立即写入，窗口尺寸在正常关闭时写入；启动由
  `SetupMainWindow.restore_ui_state` 读取并应用。
- 加载优先级为 **user.yaml > 品牌覆盖层 > 基座默认值**；用户文件只记录改动过
  的键，未出现的字段继续使用下层配置。
- 文件缺失、YAML 损坏、顶层结构错误或字段值非法时记录告警并回退默认值；写入
  失败不影响当前会话，并采用临时文件 + 原子替换避免半截文件。
- 用户偏好存储由 `ui_state.json` 改为 YAML 覆盖层；首次启动会自动把旧 JSON
  中的主题 / 语言 / 窗口尺寸迁移到 `user.yaml`，旧文件保留但不再读取。
- 修复启动恢复非默认语言后，应用菜单语言包仍按默认语言注入的问题；修复
  Overlay 菜单在窗口缩放时错误访问 `CWindow` 导致崩溃的问题。

### 后续修复（2026-11-09，未发版）

- **install-demo 覆盖前安全校验（FIX-01）**：`--force` 覆盖前校验源/目标目录不相交、拒绝符号链接目标，复制失败返回非 0 且不残留半截目录，避免源码树默认路径自毁内置示例。
- **doctor 安全诊断（FIX-03）**：默认只发现应用、不执行插件入口代码，新增 `--load`（显式加载）与 `--allow-external`（放行外部目录）；`--apps-dir` 归属校验、加载/发现失败返回非 0，并修正模块 docstring 对 PySide6 传递导入的说明。
- **用户配置高版本回写与完整性（FIX-02）**：`save_user_settings()` 回写保留磁盘原 `schema_version` 与所有未知键、绝不降级；`_migrate_state()` 补 v1→v2→v3 迁移与 v3 背景字段默认值；`_write_atomic()` 改用 `mkstemp` 唯一临时文件 + `fsync` + `os.replace`，落盘失败日志保留具体异常类型与消息。
- **主题订阅与配置上下文一致性（FIX-07）**：`unsubscribe()` 对绑定方法改用等价比较、`_notify()` 清理失效弱引用、`_lock` 改 `RLock` 且 `apply()` 锁内更新状态/锁外通知、`cycle()` 对非序列主题回退首项；`ColorHandler.update()` 持模块级 `RLock`；`ConfigContext` 改用 `_ContextData` 快照一次性发布，读侧不再看到 `None` 或半初始化状态。
- **错误协议与遥测健壮性（FIX-08）**：`AppError` 补 `Exception.__init__` 使 `args` 非空且 `__str__` 格式不变；配置注册表把 `IOErrorBoundary` 统一包装为 `DomainErrorBoundary`；`events.jsonl` 超阈值轮转并只留 1 份备份，`record_event()` 兜底 `OSError` / `TypeError` / `ValueError`。
- **配置契约修正（FIX-06）**：`configure()` 在上下文已加载时（含 `reset_config()` 后的首次调用）即抛 `ConfigAlreadyLoadedError`，不再静默失效；`env_fallback` 改用 `None` 哨兵保留上次值；`resource_dirs` 传空序列可清空覆盖层；`apps_root()` 与遥测目录统一走 `resolved_*()` helper，不再绕过开关直读环境变量。
- **应用重载幂等与失败隔离（FIX-09）**：`reset_apps_cache()` / `load_apps(force=True)` 改为按本轮登记的 `plugin_id` 定向清理全局 `PluginRegistry`（禁止整体 reset，保住内置菜单），重载不再触发 `PLUGIN_DUPLICATE_MENU`；菜单注册后置到入口 `exec_module` 成功之后、失败应用按差集回收已注册项避免孤儿菜单，入口导入失败回滚 `sys.modules` 半初始化模块。
- **清单校验与路由去重（FIX-12）**：缺 `app_name` 的回退值写回 `config`；`show_top` / `is_active` / `is_default` 统一走 `_as_bool()`（`show_top: "false"` 正确解析为 `False`）；`build_page_routes()` 遇到重复 `button_id` 抛 `PLUGIN_DUPLICATE_BUTTON_ID`，并重写 `test_page_registry.py` 恒真断言为带自检的真实列表比对。
- **语言切换页面重翻译与失败回滚（FIX-11）**：`_retranslate_pages()` 跳过 `Main_Page` / `widget_show` 两个占位 QWidget，并为实现 `retranslateUi()` 的第三方页面提供按签名适配的局部刷新（基座内置预览页未提供 `retranslate()`，默认仍走整页重建）；`apply_language()` 改为刷新成功才写 `user.yaml`，失败回滚到 `Language.apply(previous)`、记录 warning、不落盘并返回旧语言名；`AppContext.language` 回落 `Language.current()` 而非静态配置值；补齐 v2 的 `on_language_changed` / `on_unload` 调用点并做异常隔离。
- **CI 触发与发布门禁对齐（FIX-04）**：发布流水线 tag 前缀由 `v*` 改为 `base-v*`，与 `CHANGELOG.md` 的 `base-v1.0.0` 及 `docs/contributing.md` 的 `git tag base-v1.0.0` 对齐；发布侧质量检查改为与 `.workflow/QualityGate.yml` 完全一致的全仓 ruff + mypy + pytest 覆盖率 70% 门禁。历史 `v*` tag 保留、不删除，也不再触发发布。

#### 破坏性变更（B4）

| 变更 | 迁移方式 |
| --- | --- |
| 移除 `configure(..., strict_plugins=...)` 参数与 `AppConfig.strict_plugins` 字段（FIX-10） | 调用方删除该参数即可；基座从未读取该值，移除前后行为无变化 |

> 注：FIX-06 对 `configure()` 调用时机的修正（上下文已加载时首次 `configure()` 即抛
> `ConfigAlreadyLoadedError`）属于**行为变更**，不是破坏性 API 变更；此前依赖「静默失效」的调用
> 需改在 `get_app_context()` 之前配置，或显式传 `force_reload=True`。

本轮修复详见 docs/CHANGE_PLAN.md。

本轮 12 项修复全部完成，逐项 commit 与验证结果见 `docs/CHANGE_PLAN.md` §7。

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
- **版本号**：`sllkgui.__version__` 改为以 `_version.py` 为唯一来源，源码树不再显示
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
| 移除浮层版 `CDrawer`（`sllkgui.guicore.CDrawer`） | 改用四向栏目：左右列由主窗口装配，顶/底列用 `CTopColumn` / `CBottomColumn`；开合用 `MainFunctions.toggle_*_column(window)` |

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

- `sllkgui.window` 门面、`sllkgui.configure()`、`sllkgui` 命令行（`run` / `install-demo` /
  `examples` / `doctor`）、`AppHandle`、`py.typed`。
- 内置示例与最小工程随 wheel 分发（`force-include`）。

## 历史版本摘要

| 版本 | 主题 |
| --- | --- |
| `0.2.4` | PyCL2 基座能力回流：页面懒加载、主题强调色覆盖、标题栏信号 sender 修复、语言订阅清理 |
| `0.2.3` 及更早 | 早期组件与窗口骨架迭代；细节见 git 历史 |

> 更早的逐条修复记录已从本文件移除，需要追溯时使用 `git log -- CHANGELOG.md`。
