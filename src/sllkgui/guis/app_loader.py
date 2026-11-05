"""Apps 应用模组加载器：从 ``Apps/`` 目录发现并挂载应用。

应用模组协议（每个 ``Apps/<app_name>/`` 是一个自包含模组）::

    Apps/<app_name>/
    ├── config.yml               # 应用清单（app_name/protocol/core/button_id/...）
    ├── app.py                   # 可选：v2 插件入口（导出 AppPlugin 子类）
    ├── resource/                # 应用私有资产（图标、应用菜单文案）
    │   ├── icon/app_icon.svg
    │   └── lang/{zh_cn,en_us}.yml
    ├── brand/sllkgui/          # 可选：品牌覆盖层（主题/语言/图标）
    ├── <core>/                  # 可选：逻辑层目录（清单 core 声明，零 Qt 依赖）
    └── gui/
        ├── main.py              # 页面实现（协议见下）
        └── style.py             # 可选：应用私有样式

**协议 v2（推荐）**——``protocol: 2``，入口导出 :class:`AppPlugin` 子类::

    class MyApp(AppPlugin):
        def on_load(self, ctx): ...
        def pages(self) -> list[AppPage]: ...

页面声明式给出，**入栈由基座负责**，``build(ctx, window)`` 两个参数永远都在。

**协议 v1（历史，保持兼容）**——``gui/main.py`` 按优先级识别其一：

1. ``register_plugins(registry, app)`` —— 完全自由注册（多页面应用）；
2. ``PAGE`` —— 含 ``load_page(window)`` 方法的类或实例；
3. ``build_page(app) -> QWidget`` —— 最简形态，返回页面控件。

``app`` 是 :class:`AppContext`（清单、目录、图标、语言访问）。

清单可选的校验字段：

- ``protocol``：``1``（缺省）或 ``2``；其他值报 ``APP_PROTOCOL_UNSUPPORTED``；
- ``core``：逻辑层目录名，必须存在，否则报 ``APP_CORE_MISSING``；
- ``plugin``：v2 入口符号名（入口里有多个 ``AppPlugin`` 子类时用来消歧）。

``app_name`` 必须与目录名一致，否则报 ``APP_NAME_MISMATCH``——不一致会让
应用内部的跨目录导入静默失效。

语言文件内容整体挂在 ``Language.app.<app_name>`` 命名空间下，
菜单文本通过 ``language.app.<app_name>.<key>`` 资源键引用。

本模块只做**编排**，具体职责在：

- :mod:`app_manifest`：发现目录、读清单、装语言、解析图标与入口；
- :mod:`app_namespace`：把 ``<app>/`` 目录当包导入的私有命名空间；
- :mod:`app_v2`：``AppPlugin`` / ``AppPage`` 声明到菜单/页面插件的翻译；
- :mod:`app_context`：``AppContext`` / ``AppHandle`` 两份数据；
- :mod:`app_state`：跨模块共享的加载状态。
"""

from __future__ import annotations

from pathlib import Path

from sllkgui.appcore import (
    PROTOCOL_VERSION,
    AppPluginError,
    AppSettings,
    Attrs,
    Language,
    Logger,
    MenuPlugin,
    PagePlugin,
    get_plugin_registry,
    record_event,
    to_attrs,
)

from . import app_state
from .app_context import AppContext, AppHandle
from .app_manifest import (
    _absolute_dir,
    _check_core,
    _check_name,
    _load_app_lang_data,
    _manifest_protocol,
    _resolve_entry,
    _resolve_icon,
    apply_apps_language,
    collect_app_languages,
    discover_app_dirs,
    load_app_manifest,
)

# 私有命名的再导出：内部检查（测试/诊断）仍可从 app_loader 拿到，
# 但它们是**非公开契约**，消费方请走 load_app_handles()。
from .app_namespace import _APP_NAMESPACE as _APP_NAMESPACE
from .app_namespace import _import_app_module
from .app_namespace import _NamespacePackageFinder as _NamespacePackageFinder
from .app_v2 import _instantiate_plugin, _register_v2_pages


def register_app(app_dir: Path, registry=None, *, with_handle: bool = False) -> AppContext | AppHandle | None:
    """注册单个应用：解析清单 -> 校验 -> 注册菜单插件 -> 装载页面协议 -> 注册页面插件。

    支持两种协议（由清单 ``protocol`` 字段选择，缺省 ``1``）：

    - **v2**：入口模块导出 ``AppPlugin`` 子类（见 :mod:`app_protocol`）；
    - **v1**：``register_plugins`` / ``PAGE`` / ``build_page`` 三选一（保持原样）。

    返回 AppContext（应用无页面入口时仍注册菜单并返回上下文）。
    """
    app_dir = _absolute_dir(app_dir)
    registry = registry or get_plugin_registry()
    config = load_app_manifest(app_dir)
    protocol = _manifest_protocol(config)
    name = _check_name(config, app_dir)
    core_name = _check_core(config, app_dir)
    button_id = config.get("button_id") or f"app_{name}"
    page_object = config.get("page_object") or f"{name}Page"
    target = config.get("app_target") or "LeftMenu"
    text_key = config.get("app_text") or f"language.app.{name}.app_text"
    tooltip_key = config.get("app_tooltip") or f"language.app.{name}.app_tooltip"
    icon_path = _resolve_icon(config, app_dir)
    is_default = bool(config.get("is_default", False))

    # 注入本应用语言：保证 app.lang_text 与菜单文本解析立即可用
    # （语言切换时由 Language.apply -> _app_language_provider 整体重建）
    app_node = getattr(Language, "app", None) or Attrs()
    app_node[name] = to_attrs(_load_app_lang_data(app_dir, AppSettings.language))
    Language.app = app_node

    registry.register_menu(
        MenuPlugin(
            plugin_id=config.get("app_id") or f"app.menu.{target.lower()}.{name}",
            target=target,
            item={
                "btn_icon": icon_path,
                "btn_id": button_id,
                "btn_text": text_key,
                "btn_text_fallback": name,
                "btn_tooltip": tooltip_key,
                "show_top": bool(config.get("show_top", True)),
                "is_active": bool(config.get("is_active", False)),
            },
        )
    )

    context = AppContext(
        name=name,
        app_dir=app_dir,
        config=config,
        icon_path=Path(icon_path) if Path(icon_path).is_file() else None,
        core_name=core_name,
    )

    entry_file, entry_module_name = _resolve_entry(protocol, app_dir, name)
    if entry_file is None:
        Logger.warning(f"应用缺少页面实现: {name} (app.py 或 gui/main.py)")
        return AppHandle(name=name, module=None, context=context) if with_handle else context

    module = _import_app_module(entry_module_name, app_dir, entry_file)
    context.module_name = entry_module_name
    handle = AppHandle(name=name, module=module, context=context)
    finish = (lambda: handle) if with_handle else (lambda: context)

    # --------------------------------------------------------------
    # 协议 v2：AppPlugin 类入口
    # --------------------------------------------------------------
    if protocol == PROTOCOL_VERSION:
        plugin = _instantiate_plugin(module, config)
        if plugin is None:
            raise AppPluginError(
                "APP_PLUGIN_MISSING",
                f"清单 protocol=2，但 {entry_file} 没有导出 AppPlugin 子类"
                "（可写 PLUGIN = MyApp() 或定义一个 AppPlugin 子类）",
            )
        plugin._bind(context)  # noqa: SLF001 - 加载器与协议的内部契约
        plugin.on_load(context)
        pages = list(plugin.pages() or [])
        if not pages:
            Logger.warning(f"应用 {name} 声明了 protocol=2，但没有返回任何页面")
        _register_v2_pages(plugin, pages, registry, context, config)
        handle.plugin = plugin
        Logger.info(f"应用注册完成: {name} (v2, {len(pages)} 页)")
        return finish()

    # --------------------------------------------------------------
    # 协议 v1（历史）：register_plugins > PAGE > build_page
    # --------------------------------------------------------------
    if callable(getattr(module, "register_plugins", None)):
        module.register_plugins(registry, context)
        Logger.info(f"应用注册完成: {name} (register_plugins)")
        return finish()

    page_obj = getattr(module, "PAGE", None)
    if page_obj is not None and callable(getattr(page_obj, "load_page", None)):
        loader = page_obj.load_page
        Logger.debug(f"应用注册完成: {name} (PAGE)")
        registry.register_page(
            PagePlugin(
                plugin_id=f"app.page.{name}",
                button_id=button_id,
                page_object=page_object,
                title_getter=lambda language: language.resolve_key(text_key, name),
                loader=loader,
                default=is_default,
            )
        )
        return finish()

    if callable(getattr(module, "build_page", None)):

        def _loader(window):
            widget = module.build_page(context)
            if widget is not None:
                window.ui.load_pages.pages.addWidget(widget)

        Logger.debug(f"应用注册完成: {name} (build_page)")
        registry.register_page(
            PagePlugin(
                plugin_id=f"app.page.{name}",
                button_id=button_id,
                page_object=page_object,
                title_getter=lambda language: language.resolve_key(text_key, name),
                loader=_loader,
                default=is_default,
            )
        )
        return finish()

    Logger.warning(f"应用缺少页面入口: {name} (需导出 PAGE / build_page / register_plugins)")
    return finish()


def load_apps(root: str | Path | None = None, force: bool = False) -> list[Path]:
    """发现并注册全部应用（幂等：重复调用直接返回缓存），返回应用目录列表。

    - 单个应用加载失败不影响其余应用；
    - 完成后注入当前语言的全部应用语言包。

    需要按名字取应用模块时用 :func:`load_app_handles`——不要自己拼模块路径，
    应用模块位于私有命名空间下。
    """
    if app_state.loaded and not force:
        return app_state.app_dirs

    app_dirs = discover_app_dirs(root)
    app_state.app_dirs = app_dirs

    registry = get_plugin_registry()
    loaded = 0
    handles: list[AppHandle] = []
    for app_dir in app_dirs:
        try:
            handle = register_app(app_dir, registry=registry, with_handle=True)
            if isinstance(handle, AppHandle):
                handles.append(handle)
            loaded += 1
        except Exception as exc:
            Logger.error(f"应用加载失败: {app_dir.name}: {exc}")
            record_event(
                "app.load_error",
                category="app",
                level="error",
                payload={"app": app_dir.name, "error": str(exc)},
            )

    app_state.handles = handles
    # 用当前生效语言（可能已由用户配置恢复）而不是 AppSettings 默认值，
    # 否则基座文案切到 en_us 后，应用菜单仍会被注入 zh_cn 的语言包。
    apply_apps_language(Language.current(), app_dirs)
    app_state.loaded = True
    Logger.info(f"应用加载完成: {loaded}/{len(app_dirs)}")
    record_event("apps.loaded", category="app", payload={"total": len(app_dirs), "loaded": loaded})
    return app_dirs


def load_app_handles(root: str | Path | None = None, force: bool = False) -> list[AppHandle]:
    """发现并注册全部应用，返回句柄列表（``name`` -> 模块 + 上下文）。

    这是消费方（宿主应用）取自身业务模块的**唯一正路**：
    ``{h.name: h for h in load_app_handles()}``。
    """
    load_apps(root, force=force)
    return list(app_state.handles)


def get_app_handle(name: str, root: str | Path | None = None) -> AppHandle | None:
    """按应用名取句柄；未加载时先加载。找不到返回 ``None``。"""
    load_apps(root)
    for handle in app_state.handles:
        if handle.name == name:
            return handle
    return None


def reset_apps_cache() -> None:
    """重置加载标记（测试/热重载场景使用）。"""
    app_state.loaded = False
    app_state.app_dirs = []
    app_state.handles = []


__all__ = [
    "AppContext",
    "AppHandle",
    "apply_apps_language",
    "collect_app_languages",
    "discover_app_dirs",
    "get_app_handle",
    "load_app_handles",
    "load_app_manifest",
    "load_apps",
    "register_app",
    "reset_apps_cache",
]
