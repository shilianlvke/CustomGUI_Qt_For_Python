# API 速查

内测期只保证**门面**的名字稳定：`customgui`、`customgui.config`、`customgui.appcore`、
`customgui.window`、`customgui.guicore`。`customgui.appcore.sysx.*`、`customgui.guis.*`
属于内部实现，可能重组，宿主代码不应直接依赖。

签名以源码为准；本文件只列常用入口，完整清单看各包 `__all__`。

## 1. 稳定面一览

| 入口 | 提供 |
| --- | --- |
| `customgui` | `configure()` / `current_config()` / `reset_config()` / `__version__` / `package_root()` / `resource_root()` |
| `customgui.appcore` | 配置视图、主题、语言、令牌、插件协议、错误边界、遥测、存储工具 |
| `customgui.window` | 窗口骨架、应用装载、语言服务 |
| `customgui.guicore` | 组件、窗口部件、页面基类 `CPreviewPage`、样式、字体、后台任务、回调守卫 |

## 2. 配置

```python
def configure(
    *,
    apps_dir: str | os.PathLike | None = None,
    resource_dirs: Sequence[str | os.PathLike] | None = None,
    data_dir: str | os.PathLike | None = None,
    diagnostics_dir: str | os.PathLike | None = None,
    builtin_menus: bool | None = None,
    strict_plugins: bool | None = None,
    env_fallback: bool = True,
    force_reload: bool = False,
) -> AppConfig: ...
```

- 传 `None` 的字段保持默认（或环境变量兜底），不会被清空。
- 优先级：显式参数 > `CUSTOMGUI_*` 环境变量 > 内置默认值。
- 配置上下文已加载后再调用且未传 `force_reload=True`，抛 `ConfigAlreadyLoadedError`。

```python
from customgui import current_config, reset_config

cfg = current_config()          # 当前生效配置
reset_config()                  # 清空（主要给测试用）
```

环境变量：`CUSTOMGUI_APPS_DIR`、`CUSTOMGUI_RESOURCE_DIR`、`CUSTOMGUI_ROOT_DIR`、
`CUSTOMGUI_DATA_DIR`、`CUSTOMGUI_DIAGNOSTICS_DIR`、`CUSTOMGUI_BUILTIN_MENUS`。

## 3. 配置视图与上下文

```python
from customgui.appcore import (
    AppSettings, AppLanguages, AppThemes, AppOthers,
    get_app_context, apps_root, ColorPalette, Language, PathFactory,
)

get_app_context(force_reload=False)     # 首次调用时惰性加载并校验
AppSettings.theme_name                  # -> "default"
AppSettings.startup_size                # -> (960, 540)
AppSettings.lef_menu_size               # -> SizeRange(minimum=..., maximum=...)
AppThemes["dracula"].data               # -> Attrs
AppLanguages["zh_cn"].data
apps_root()                             # -> Path
```

`Attrs` 同时支持属性与字典访问：`node.key` / `node["key"]`，缺失时返回空 `Attrs()` 而不是抛错。

路径工具（`customgui.appcore.sysx.config.paths`，内部模块但常用）：

| 函数 | 作用 |
| --- | --- |
| `resource_roots()` | 按优先级返回资源根（其下有 `customui/`） |
| `find_resource(rel)` / `resolve_path(rel)` | 在资源根中查找 / 解析为绝对路径 |
| `iter_files(dir, suffix)` | 同名只保留最高优先级那份 |
| `iter_file_layers(dir, suffix)` | 返回每层的同名文件，供配置深合并 |
| `apps_root()` / `data_root()` | 应用目录 / 可写数据根 |

### 用户配置持久化

运行时修改的外观偏好写入 `<data_root>/settings/user.yaml`（默认落在程序运行
根目录下的 `settings/user.yaml`，可用 `configure(data_dir=...)` 或
`CUSTOMGUI_DATA_DIR` 覆盖），只记录改动过的键：

| 字段 | 来源 | 写入时机 |
| --- | --- | --- |
| `theme_name` | 主题卡片 / 深色模式 | 主题切换后立即写入 |
| `language` | 外观配置语言选择 | 语言切换完成后立即写入 |
| `menu_mode` | Static / Overlay | 切换后立即写入 |
| `startup_size` | 窗口尺寸 | 正常关闭窗口时写入（最大化/最小化/全屏跳过） |
| `acrylic_transparency` | 外观配置「窗口透明度」滑块 | 拖动过程中节流写入，松手再落盘一次 |
| `glass_strength` | 外观配置「亚克力质感强度」滑块 | 拖动过程中节流写入，松手再落盘一次 |

```python
from customgui.appcore import load_user_settings, save_user_settings, user_settings_path

load_user_settings()                        # 启动时读取（已校验，缺失返回 {}）
save_user_settings(theme_name="bright")     # 手动写入，失败返回 False 且不影响会话
user_settings_path()                        # -> Path
```

优先级：**user.yaml > 品牌覆盖层（`apps/<app>/brand`）> 基座默认 `settings/*.yaml`**。
用户文件缺失、YAML 损坏、顶层不是字典或字段值非法时回退下层配置；写入使用
临时文件 + 原子替换，失败只记录告警。首次读取且 `user.yaml` 不存在时，会
自动迁移旧版 `ui_state.json` 中的主题 / 语言 / 窗口尺寸。

## 4. 主题与令牌

```python
from customgui.appcore import get_theme_manager, get_design_tokens, ColorPalette

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
from customgui.appcore import Language, LANGUAGE_OPTIONS
from customgui.window import apply_language, available_languages, current_language

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

## 6. 插件

```python
from customgui.appcore import (
    AppPlugin, AppPage, AppPluginError, PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS,
    PluginRegistry, MenuPlugin, PagePlugin, CommandPlugin,
    get_plugin_registry,
)

registry = get_plugin_registry()
registry.register_menu(MenuPlugin(...))
registry.register_page(PagePlugin(...))
registry.load_page_plugin(page_object)     # 按需构建页面
registry.build_page_routes(language)       # button_id -> (page_object, title)
registry.has_page(page_object)
registry.page_plugins / menu_plugins / command_plugins
registry.disable_plugin(plugin_id) / enable_plugin(plugin_id)
```

插件协议与清单字段见 [PLUGIN.md](PLUGIN.md)。

## 7. 错误边界

```python
from customgui.appcore import (
    AppError, DomainErrorBoundary, IOErrorBoundary, UIErrorBoundary, to_user_message,
)

raise AppError("APP_CORE_MISSING", "缺少逻辑层", layer="domain", details="core 目录不存在")
to_user_message(exc)     # -> 可直接展示的中文文案
```

`AppError` 字段：`code`、`message`、`layer`、`details`（字符串）。三个边界分别负责领域错误、IO 错误、
UI 错误；边界内部记录遥测，但不吞掉 `KeyboardInterrupt` / `SystemExit`。

## 8. 遥测与日志

```python
from customgui.appcore import record_event, track_timing, read_recent_events, Logger

record_event("app.ready", category="app", level="info", payload={"theme": "default"})
with track_timing("app.config_load", category="perf"):
    ...
read_recent_events(limit=20)      # -> list[dict]
Logger.debug("...") / Logger.warning("...") / Logger.error("...") / Logger.exception("...")
```

事件写到 `diagnostics_dir`（默认 `<data_root>/logs/diagnostics`），JSONL 追加；
日志写到 `<data_root>/logs/`。数据目录不可写时降级到控制台，不阻塞启动。

## 9. 存储与并发

```python
from customgui.appcore.tool import (
    read_json, write_json, read_text, write_text, StoreError,
)

write_json(path, data, backup=True)     # 临时文件 + fsync + os.replace，失败回退 .bak
read_json(path, default=None)
```

```python
from customgui.guicore import run_task, TaskWorker, ProgressUpdate, active_tasks

task = run_task(owner, fn, on_done=..., on_error=..., on_progress=..., on_cancelled=...)
task.cancel()
```

```python
from customgui.guicore import safe_callback, ui_callback, single_shot

safe_callback(fn)              # 控件已析构时静默返回
ui_callback(owner, fn)         # 绑定 owner 生命周期
single_shot(owner, 200, fn)    # 宿主销毁后不再触发
```

## 10. 窗口门面

```python
from customgui.window import (
    UiMainWindow, SetupMainWindow, MainWindowController, MainFunctions,
    Ui_MainPages, Ui_LeftColumn, Ui_RightColumn,
    AppContext, AppHandle, discover_app_dirs, load_apps, load_app_handles,
    get_app_handle, load_app_manifest, register_app, reset_apps_cache,
    apply_language, available_languages, current_language,
)

load_apps(root=None, force=False)          # 发现 + 注册全部应用，返回已注册的应用目录列表
load_app_handles(root=None)                # 同上，返回 AppHandle 列表
get_app_handle("button_preview")           # 按名字取已加载应用（不存在返回 None）
discover_app_dirs(root=None)               # 只发现，不注册
```

窗口装配顺序（`customgui run` 与宿主 `main.py` 一致）：

```python
ui = UiMainWindow(); ui.setup_ui(window)
SetupMainWindow.setup_gui(window)
controller = MainWindowController(window)
```

单页面应用可以直接继承预览页基类，省掉滚动容器、卡片与标题样式的样板：

```python
from customgui.guicore import CPreviewPage


class MyPage(CPreviewPage):
    slug = "my_app"           # 语言命名空间 app.my_app；objectName 推导为 myAppPage
    columns = 3               # 分区内默认每行控件数
    title_scale = "subtitle"  # 分区标题字号：subtitle（默认）或 title

    @classmethod
    def sections(cls, page, window):
        # 条目三种写法：(标题, 控件) / (标题, [控件...], 每行列数) / 现成 QWidget
        return [(cls.tr("group_a"), [widget_a, widget_b], 2)]


PAGE = MyPage
```

`slug` 决定语言命名空间与 `page_object`，须与清单 `config.yml` 的 `page_object` 一致
（`tests/test_preview_apps.py` 会校验）。钩子都是 `classmethod`，因此 `PAGE` 写成类或实例
都能被加载器正确调用。

## 11. 样式与字体

```python
from customgui.guicore import Styles, install_fonts, install_system_fonts

Styles()                       # 生成当前主题的全局 QSS 字符串
install_fonts(["assets/font.ttf"])   # 返回成功加载的数量
install_system_fonts()               # 注册系统字体，缓解 offscreen / 远程会话豆腐块
```

## 12. 版本与兼容

- 版本单一来源：`src/customgui/_version.py`。`customgui.__version__` **先读该文件**，
  只有文件缺失时才回落到已安装元数据——反过来会让源码树显示 site-packages 里旧 wheel 的版本号。
- 已下线的历史入口由 `tests/test_removed_entry_points.py` 守着，不得复活。
- `0.x` 内测期允许 minor 版本破坏兼容，破坏性变更必须写入 [CHANGELOG](../CHANGELOG.md)。
