# API 速查

公开 API 只保证**门面**的名字稳定：`sllkgui`、`sllkgui.config`、`sllkgui.appcore`、
`sllkgui.plugin`、`sllkgui.window`、`sllkgui.guicore`。`sllkgui.appcore.sysx.*`、
`sllkgui.guis.*`、`sllkgui.gallery.*` 属于内部实现，可能重组，宿主代码不应直接依赖。

`sllkgui.guicore.window` 下的窗口部件可直接使用；其中 `window/window/` 与
`guis/windows/` 是组件内部装配，未来可能调整。完整稳定面见下表，其余导出符号
属于“可以使用但不承诺长期稳定”的组件内部约定。

签名以源码为准；本文件只列常用入口，完整清单看各包 `__all__`。

## 1. 稳定面一览

| 入口 | 提供 |
| --- | --- |
| `sllkgui` | `configure()` / `current_config()` / `reset_config()` / `__version__` / `package_root()` / `resource_root()` |
| `sllkgui.appcore` | 配置视图、主题、语言、设计令牌、设置 schema 与存储、错误边界、遥测 |
| `sllkgui.plugin` | 插件作者门面：`Plugin` / `GalleryContext` / `Permission` / 设置与托盘、快捷键类型 |
| `sllkgui.window` | 窗口骨架、Gallery 装载（`load_gallery` / `load_run`）、语言服务 |
| `sllkgui.guicore` | 组件、窗口部件、页面基类 `CPreviewPage`、样式、字体、后台任务、回调守卫、快捷键表、桌面宠物 `MihoutaoPetController` |

## 2. 配置

```python
def configure(
    *,
    gallery_dir: str | os.PathLike | None = None,
    resource_dirs: Sequence[str | os.PathLike] | None = None,
    data_dir: str | os.PathLike | None = None,
    diagnostics_dir: str | os.PathLike | None = None,
    builtin_menus: bool | None = None,
    pip_index_url: str | None = None,
    env_fallback: bool | None = None,
    force_reload: bool = False,
) -> AppConfig: ...
```

- `gallery_dir` / `data_dir` / `diagnostics_dir` / `builtin_menus` 传 `None` 时保留上次 `configure()` 的值（首次为 `None`，由环境变量或默认值回落）。
- `resource_dirs` 传 `None` 保留上次值，传空序列清空覆盖层；`env_fallback` 传 `None` 保留上次值，设为 `False` 时不再用 `SLLKGUI_*` 环境变量兜底。
- 优先级：显式参数 > `SLLKGUI_*` 环境变量 > 内置默认值（环境变量仅在 `env_fallback` 打开时兜底）。
- 配置上下文已加载后再调用且未传 `force_reload=True`，抛 `ConfigAlreadyLoadedError`。

```python
from sllkgui import current_config, reset_config

cfg = current_config()          # 当前生效配置
reset_config()                  # 清空（主要给测试用）
```

环境变量：`SLLKGUI_GALLERY_DIR`、`SLLKGUI_RESOURCE_DIR`、`SLLKGUI_ROOT_DIR`、
`SLLKGUI_DATA_DIR`、`SLLKGUI_PROGRAM_DIR`、`SLLKGUI_PIP_INDEX_URL`。

## 3. 配置视图与上下文

```python
from sllkgui.appcore import (
    AppSettings, AppLanguages, AppThemes, AppOthers,
    get_app_context, ColorPalette, Language, PathFactory,
)

get_app_context(force_reload=False)     # 首次调用时惰性加载并校验
AppSettings.theme_name                  # -> "default"
AppSettings.startup_size                # -> (960, 540)
AppSettings.lef_menu_size               # -> SizeRange(minimum=..., maximum=...)
AppThemes["dracula"].data               # -> Attrs
AppLanguages["zh_cn"].data
```

`Attrs` 同时支持属性与字典访问：`node.key` / `node["key"]`，缺失时返回空 `Attrs()` 而不是抛错。

路径工具（`sllkgui.appcore.sysx.config.paths`，内部模块但常用）：

| 函数 | 作用 |
| --- | --- |
| `resource_roots()` | 按优先级返回资源根（其下有 `sllkgui/`） |
| `find_resource(rel)` / `resolve_path(rel)` | 在资源根中查找 / 解析为绝对路径 |
| `iter_files(dir, suffix)` | 同名只保留最高优先级那份 |
| `iter_file_layers(dir, suffix)` | 返回每层的同名文件，供配置深合并 |
| `gallery_root()` / `data_root()` | 插件安装目录 / 可写数据根 |

### 用户配置持久化

运行时修改的外观偏好写入 `<data_root>/settings/user.yaml`（默认落在程序运行
根目录下的 `settings/user.yaml`，可用 `configure(data_dir=...)` 或
`SLLKGUI_DATA_DIR` 覆盖），只记录改动过的键。文件首行带
`schema_version`（当前为 `7`）；缺失该键按 v1 读取，高于当前版本时只读取
已知字段并告警，**回写时保留原版本号与所有未知键、绝不降级**：

| 字段 | 来源 | 写入时机 |
| --- | --- | --- |
| `theme_name` | 设置窗口「外观」主题卡片 | 点「保存」时写入 |
| `language` | 设置窗口「界面」语言选择 | 点「保存」时写入 |
| `menu_mode` | 左菜单 Static / Overlay | 点「保存」时写入 |
| `drawer_mode` | 四向抽屉 Static / Overlay | 点「保存」时写入 |
| `acrylic_transparency` / `glass_strength` | 材质滑块 | 点「保存」时写入 |
| `settings_acrylic` | 设置页亚克力开关（默认 `true`） | 点「保存」时写入 |
| `background_image` / `background_fit` / `background_blur` | 背景设置 | 点「保存」时写入 |
| `background_recent` | 最近使用的背景图 | 选择背景图时写入，最多 5 条并自动去重 |
| `remember_window_size` | 启动与窗口 | 点「保存」时写入 |
| `startup_size` | 窗口尺寸 | 正常关闭且「记住窗口尺寸」开启时写入（最大化/最小化/全屏跳过） |

插件配置独立存放在 `<data_root>/settings/plugins/<plugin_id>.yaml`，每个插件
一个文件，键为 `plugin.<plugin_id>.<key>`；详见 `docs/SETTINGS.md`。

### 统一设置

```python
from sllkgui.appcore import (
    SettingsSession, SettingsPage, SettingsSection, Setting,
    ensure_core_pages, settings_registry,
)

ensure_core_pages()                 # 幂等：注册基座三张页
session = SettingsSession()         # 读取当前注册表 + 存储
session.set("core.appearance.theme", "bright")
session.save()                      # 按命名空间写入，失败保留脏值
session.discard()                   # 放弃未保存改动

# 插件侧（见 docs/SETTINGS.md）
ctx.settings.define(SettingsPage(page_id="", title="插件设置", sections=(...)))
ctx.settings.get("key", default)
ctx.settings.set("key", value)
```

公开类：`SettingsSession`、`SettingsRegistry`、`SettingsStore`、`SettingSpec`
（别名 `Setting`）、`SettingsPage`、`SettingsSection`、`SettingOption`、
`SettingsError` / `SettingsConflictError` / `SettingsValidationError`。
窗口：`sllkgui.guicore.CSettingsWindow`。

```python
from sllkgui.appcore import load_user_settings, save_user_settings, user_settings_path

load_user_settings()                        # 启动时读取（已校验，缺失返回 {}）
save_user_settings(theme_name="bright")     # 手动写入，失败返回 False 且不影响会话
user_settings_path()                        # -> Path
```

优先级：**user.yaml > 品牌覆盖层（`configure(resource_dirs=...)` 指定的资源目录）> 基座默认 `settings/*.yaml`**。
用户文件缺失、YAML 损坏、顶层不是字典或字段值非法时回退下层配置；写入使用
`mkstemp` 生成的同目录唯一临时文件 + `fsync` + `os.replace` 原子替换，失败记录
告警（含具体异常类型与消息）且不影响当前会话，回写保留磁盘原始版本与未知键。
首次读取且 `user.yaml` 不存在时，会自动迁移旧版 `ui_state.json` 中的主题 /
语言 / 窗口尺寸。`_migrate_state()` 显式记录 v1→v2→v3 跃迁，v3 的
`background_*` 默认值按需补齐且不覆盖已有键。

## 4. 主题与令牌

```python
from sllkgui.appcore import get_theme_manager, get_design_tokens, ColorPalette

manager = get_theme_manager()
manager.current()                       # 当前主题名
manager.apply("eye", accent="#22c55e")  # 切换主题，可选强调色
manager.accent                          # 当前强调色（属性）
manager.cycle()                         # 循环到下一套主题
manager.subscribe(callback)             # 主题变化回调（支持控件销毁自动解绑）
manager.unsubscribe(callback)

tokens = get_design_tokens()
tokens.colors / tokens.typography / tokens.spacing / tokens.radius / tokens.border / tokens.size
ColorPalette.update(AppThemes["default"].data)   # 底层入口，通常由 ThemeManager 调用
```

## 5. 语言

```python
from sllkgui.appcore import Language, LANGUAGE_OPTIONS
from sllkgui.window import apply_language, available_languages, current_language

Language.resolve("language.app.hello.app_text", "默认文案")
Language.resolve_key("language.UI.ui_Restore")
Language.update(AppLanguages["en_us"].data)     # 增量合并
Language.replace(AppLanguages["en_us"].data)    # 整份替换
Language.current()                              # 当前语言名
Language.register_app_provider(fn)              # 注册应用语言提供者

apply_language("en_us", window)      # 切换 + 重建页面 + 刷新标题
available_languages()                # -> ("en_us", "ja_jp", "zh_cn", "zh_tw")
```

`LANGUAGE_OPTIONS` 按资源根惰性发现：`languages/*.yaml` 有几个就有几种，`configure()` 后缓存失效。

`AppContext.language` 每次读取都取最新值：未显式赋值时跟随 `Language.current()`，
语言切换后立即返回新语言名；`ctx.language = "ja_jp"` 可显式覆盖并优先于全局值。
旧实现回落静态的 `AppSettings.language`，切语言后会读到陈旧值（FIX-11 已修正）。

`apply_language()` 只在窗口级刷新成功后才把目标语言写入 `user.yaml`；刷新抛异常时
回滚到切换前的语言、记录 warning、**不落盘**，并返回旧语言名（不抛异常）。

## 6. 插件

插件作者的门面是 `sllkgui.plugin`：

```python
from sllkgui.plugin import (
    Plugin, GalleryContext, GalleryEvents, GalleryServices, GallerySettings, GalleryStorage, GalleryShortcut, GalleryShortcuts,
    GalleryTray, GalleryToast, ToastAction, ToastDismiss, ToastHandle, ToastLevel, ToastMode, ToastResult,
    Permission, PLUGIN_API_VERSION,
    Setting, SettingOption, SettingsAction, SettingsInfo, SettingsPage, SettingsSection,
    PluginError, ShortcutBinding, ShortcutConflict, TrayEntry, TrayGroup,
)
```

提示走统一协议（`ctx.toast`）：失败也**不抛异常**，用 `handle.result.code` 判断；
详情见 [TOAST.md](TOAST.md)。

```python
ctx.toast.show("已保存", level="success", channel="editor", dedupe="restart")
handle = ctx.toast.loading("正在连接…", channel="net")
handle.succeed("连接成功")          # 或 handle.fail("连接失败", code="NET_FAILED", detail=str(exc))
```

宿主侧（加载器、注册表、存储）在 `sllkgui.gallery`：

```python
from sllkgui.gallery import (
    GalleryRegistry, GalleryStore, PluginManager, PluginRecord, SurfaceRecord,
    load_plugin, unload_plugin, discover_plugin_dirs, load_manifest,
)
```

插件协议、清单字段与生命周期见 [PLUGIN.md](PLUGIN.md)。

## 7. 错误边界

```python
from sllkgui.appcore import (
    AppError, DomainErrorBoundary, IOErrorBoundary, UIErrorBoundary, to_user_message,
)

raise AppError("APP_CORE_MISSING", "缺少逻辑层", layer="domain", details="core 目录不存在")
to_user_message(exc)     # -> 可直接展示的中文文案
```

`AppError` 字段：`code`、`message`、`layer`、`details`（字符串）。dataclass 的
`__post_init__` 会调用 `Exception.__init__`，因此 `args` 非空；`__str__()` 固定输出
`[layer:code] message (details)`，不受 `args` 影响。三个边界分别负责领域错误、IO 错误、
UI 错误；配置注册表把 `load_yaml_file()` 的 `IOErrorBoundary`（`YAML_FILE_NOT_FOUND` /
`YAML_PARSE_ERROR`）与校验 `ValueError` 统一包装为带错误码的 `DomainErrorBoundary`；
边界内部记录遥测，但不吞掉 `KeyboardInterrupt` / `SystemExit`。

## 8. 遥测与日志

```python
from sllkgui.appcore import record_event, track_timing, read_recent_events, Logger

record_event("app.ready", category="app", level="info", payload={"theme": "default"})
with track_timing("app.config_load", category="perf"):
    ...
read_recent_events(limit=20)      # -> list[dict]
Logger.debug("...") / Logger.warning("...") / Logger.error("...") / Logger.exception("...")
```

事件写到 `diagnostics_dir`（默认 `<data_root>/logs/diagnostics`），JSONL 追加；
`events.jsonl` 超过 `MAX_EVENT_FILE_BYTES`（1 MiB）时轮转为 `.1` 且只保留 1 份备份，
`record_event()` 对 `OSError` / `TypeError` / `ValueError`（含 `json.dumps` 序列化异常）
一律尽力而为吞掉；日志写到 `<data_root>/logs/`。数据目录不可写时降级到控制台，
不阻塞启动。

## 9. 存储与并发

```python
from sllkgui.appcore.tool import (
    read_json, write_json, read_text, write_text, StoreError,
)

write_json(path, data, backup=True)     # 临时文件 + fsync + os.replace，失败回退 .bak
read_json(path, default=None)
```

```python
from sllkgui.guicore import run_task, TaskWorker, ProgressUpdate, active_tasks

task = run_task(owner, fn, on_done=..., on_error=..., on_progress=..., on_cancelled=...)
task.cancel()
```

```python
from sllkgui.guicore import safe_callback, ui_callback, single_shot

safe_callback(fn)              # 控件已析构时静默返回
ui_callback(owner, fn)         # 绑定 owner 生命周期
single_shot(owner, 200, fn)    # 宿主销毁后不再触发
```

## 10. 快捷键

```python
from sllkgui.guicore import (
    PRIORITY_BASE, PRIORITY_LOW, PRIORITY_NORMAL,
    KeyBinding, Scope, shortcut_registry,
)

registry = shortcut_registry()
binding = KeyBinding.parse("primary+shift+p")   # 平台无关的可移植文本
binding.display                                 # "Ctrl+Shift+P" / "⇧⌘P"
handle = registry.register(
    "demo.palette", "primary+shift+p", on_palette,
    owner="demo", scope=Scope.GLOBAL, priority=PRIORITY_NORMAL,
)
handle.set_enabled(False)       # 单条启停
handle.update(sequence="primary+p")
handle.unregister()             # 或 registry.unregister_owner("demo")
registry.set_active(False)      # 全局总开关
registry.conflicts()            # 冲突观测（序列 / 归属 / 生效者）
```

- 注册表在 `QApplication` 上装唯一事件过滤器：命中即消费，未命中放行。
- 插件请走 `ctx.shortcuts`：权限校验、`plugin_id:` 前缀与稳定错误码由基座统一处理
  （见 [SHORTCUTS.md](SHORTCUTS.md)）。

## 11. 窗口门面

```python
from sllkgui.window import (
    UiMainWindow, SetupMainWindow, MainWindowController, MainFunctions,
    Ui_MainPages, Ui_LeftColumn, Ui_RightColumn,
    GalleryWindow, load_gallery, load_run,
    apply_language, available_languages, current_language,
)
```

两种模式的入口：

```python
window = load_gallery(route="", data_dir=None)   # 组件展厅：只加载内置预览插件
window = load_run(                              # 正式模式
    route="",
    data_dir=None,
    gallery_dir=None,          # 已安装插件目录
    plugin_dirs=None,          # 额外加载的本地插件目录
    safe_mode=False,
    allow_local=False,
    install_missing_deps=True, # 缺失依赖时询问是否安装
    interactive=True,
    index_url="",
    check_tools=False,         # 启动时检测 uv / Git
    watch=False,               # 监听 plugin_dirs 下的开发插件并热重载
)
```

插件热重载入口：

```python
# 只刷新目标插件及其反向依赖者；未受影响页面保持实例
result = window.reload_plugin_in_place("com.example.notes", reason="update")
if not result.ok:
    print(result.code, result.message)

# 停用/卸载：只卸载，不重新加载
window.reload_plugin_in_place("com.example.notes", reason="disable", load=False)

# 全量重载回退（兼容旧行为）
window.reload_plugins(native_page="page_native_plugin_store")
```

窗口装配顺序（`sllkgui run` 与宿主 `main.py` 一致）：

```python
ui = UiMainWindow(); ui.setup_ui(window)
SetupMainWindow.setup_gui(window)
controller = MainWindowController(window)
```

`MainWindowController` 负责窗口状态持久化与路由；路由函数（`get_page_routes` /
`get_menu_items` / `get_default_page_object`）显式接收 `window`，不再依赖进程级注册表单例。

### 窗口背景图

```python
from sllkgui.guicore import CWindow

window.set_background_image("C:/Pictures/wall.png", "fill")  # fill / fit / stretch / tile / center
window.set_background_fit("fit")
window.background_image()   # -> 路径；空字符串表示主题纯色
window.background_fit()     # -> 当前适应模式
window.set_background_blur(18)  # 背景模糊强度 0–60 px；0 表示不模糊
window.background_blur()    # -> 当前强度
window.set_background_image("")  # 清除背景图（模糊值保留，选新图时继续生效）
```

背景图由 `CWindow.paintEvent` 绘制并按尺寸缓存缩放结果；模糊只作用于这张
背景 pixmap，不挂到窗口或子控件，宠物、文字与前景图层保持清晰。激活时各层
表面自动转为半透明（复用玻璃层参数并保留可读性下限），不会新增外层背景控件。

预览页基类拼好页面外壳（滚动容器、卡片、分区标题），子类只需实现 `sections`：

```python
from sllkgui.guicore import CPreviewPage


class MyPreviewPage(CPreviewPage):
    slug = "my_preview"           # 语言命名空间 my_preview；objectName 推导为 myPreviewPage
    columns = 3                   # 分区内默认每行控件数
    title_scale = "subtitle"      # 分区标题字号：subtitle（默认）或 title

    @classmethod
    def sections(cls, page, window):
        # 条目三种写法：(标题, 控件) / (标题, [控件...], 每行列数) / 现成 QWidget
        return [(cls.tr("group_a"), [widget_a, widget_b], 2)]
```

`slug` 决定语言命名空间与 `page_object`（留空时按 `slug` 推导）；钩子都是
`classmethod`，因此写成类或实例都能被加载器正确调用。内置预览插件的各 Surface
页面都基于它（见 `src/sllkgui/showcase/core_preview/surfaces/`）。

## 12. 样式与字体

```python
from sllkgui.guicore import Styles, install_fonts, install_system_fonts

Styles()                       # 生成当前主题的全局 QSS 字符串
install_fonts(["assets/font.ttf"])   # 返回成功加载的数量
install_system_fonts()               # 注册系统字体，缓解 offscreen / 远程会话豆腐块
```

## 13. 桌面宠物

基座原生常驻宠物（猕猴桃），启动 `sllkgui run` 时随主窗口装配；详细说明见
[PET.md](PET.md)。

```python
from sllkgui.guicore import MihoutaoPetController

pet = MihoutaoPetController()
pet.configure(tray=...)        # 可选：挂到基座托盘上
pet.start()                    # 读偏好、建引擎、按偏好显示
pet.set_state("celebrate")     # 39 态之一
pet.set_shape("gem")           # 18 果形之一
pet.set_color("violet")        # 11 色之一
pet.spin(); pet.hop(); pet.burst()
pet.shutdown()                 # 幂等
```

偏好写在 `<data_root>/settings/user.yaml` 的 `pet_*` 键（基座原生设置，出现在设置窗口原生分类）。

桌面宠物还提供进程级事件总线，供基座与插件通过事件控制宠物：

```python
from sllkgui.guicore import pet_bus
from sllkgui.guicore.pet.events import CMD_SPIN, EVT_STATE_CHANGED

events = pet_bus().handle("com.example.my_plugin")
unsubscribe = events.subscribe(EVT_STATE_CHANGED, lambda topic, payload: print(payload))
events.publish(CMD_SPIN)
unsubscribe()
```

事件命名、载荷格式、行为类型与扩展规则见 [PET_EVENTS.md](PET_EVENTS.md)。

## 14. 版本与兼容

- 版本单一来源：`src/sllkgui/_version.py`。`sllkgui.__version__` **先读该文件**，
  只有文件缺失时才回落到已安装元数据——反过来会让源码树显示 site-packages 里旧 wheel 的版本号。
- 已下线的历史入口由 `tests/test_legacy_removed.py` 与
  `tests/test_legacy_import_policy.py` 守着，不得复活。
- 同一 major 内保持向后兼容；破坏性变更只在新的 major 版本引入，并写入
  [CHANGELOG](../CHANGELOG.md)。
