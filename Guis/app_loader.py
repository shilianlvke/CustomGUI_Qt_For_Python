"""Apps 应用模组加载器：从 ``Apps/`` 目录发现并挂载应用。

应用模组协议（每个 ``Apps/<app_name>/`` 是一个自包含模组）::

    Apps/<app_name>/
    ├── config.yml               # 应用清单（app_name/app_id/button_id/...）
    ├── resource/
    │   ├── icon/app_icon.svg    # 应用图标
    │   └── lang/{zh_cn,en_us}.yml  # 应用语言文件
    └── gui/
        ├── main.py              # 页面实现（协议见下）
        └── style.py             # 可选：应用私有样式

``gui/main.py`` 页面协议（按优先级识别其一）：

1. ``register_plugins(registry, app)`` —— 完全自由注册（多页面应用）；
2. ``PAGE`` —— 含 ``load_page(window)`` 方法的类或实例（与基座历史页面风格一致）；
3. ``build_page(app) -> QWidget`` —— 最简形态，返回页面控件。

``app`` 是 :class:`AppContext`（清单、目录、图标、语言访问）。

语言文件内容整体挂在 ``Language.app.<app_name>`` 命名空间下，
菜单文本通过 ``language.app.<app_name>.<key>`` 资源键引用。
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from AppCore import (
    AppSettings,
    Attrs,
    Language,
    Logger,
    MenuPlugin,
    PagePlugin,
    YamlHandler,
    apps_root,
    get_plugin_registry,
    record_event,
    to_attrs,
)

# 已发现的应用目录缓存（语言切换时复用）
_APP_DIRS: list[Path] = []
# 全局加载标记（load_apps 幂等）
_LOADED = False


@dataclass
class AppContext:
    """传递给应用页面代码的上下文。"""

    name: str
    app_dir: Path
    config: Attrs
    icon_path: Path
    language: str

    def lang_text(self, key: str, default: Any = None) -> Any:
        """从本应用语言命名空间读取文本，如 ``lang_text("app_text")``。"""
        return Language.resolve(f"app.{self.name}.{key}", default)


def discover_app_dirs(root: str | Path | None = None) -> list[Path]:
    """扫描应用目录，返回全部含 ``config.yml`` 的子目录（按名称排序）。"""
    base = Path(root) if root is not None else apps_root()
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir() and (path / "config.yml").is_file())


def load_app_manifest(app_dir: Path) -> Attrs:
    """读取应用的 config.yml 清单。"""
    return YamlHandler(str(app_dir / "config.yml")).data


def _load_app_lang_data(app_dir: Path, language: str) -> dict:
    """读取应用的语言文件（支持 .yml/.yaml），缺失时返回空字典。"""
    for suffix in (".yml", ".yaml"):
        lang_file = app_dir / "resource" / "lang" / f"{language}{suffix}"
        if lang_file.is_file():
            return YamlHandler(str(lang_file)).to_dict()
    return {}


def collect_app_languages(language: str, app_dirs: list[Path] | None = None) -> Attrs:
    """收集全部应用的语言数据，返回 {app_name: {key: text}} 命名空间。"""
    app_node = Attrs()
    for app_dir in app_dirs if app_dirs is not None else discover_app_dirs():
        data = _load_app_lang_data(app_dir, language)
        app_node[app_dir.name] = to_attrs(data)
    return app_node


def apply_apps_language(language: str, app_dirs: list[Path] | None = None) -> None:
    """把全部应用的语言文件注入 ``Language.app.<app_name>`` 命名空间。"""
    setattr(Language, "app", collect_app_languages(language, app_dirs))
    Logger.debug(f"应用语言注入完成: {language}")


def _app_language_provider(language: str) -> dict:
    """供 Language.apply 使用的 App 语言提供者。"""
    return collect_app_languages(language, _APP_DIRS or None)


# 注册 App 语言提供者：语言切换时由 LanguageManager 自动调用
Language.register_app_provider(_app_language_provider)


def _resolve_icon(config: Attrs, app_dir: Path) -> str:
    """解析应用图标：``icon.<ns>.<filename>`` 资源键 -> 应用内图标文件绝对路径。"""
    icon_ref = config.get("app_icon") or f"icon.app.{config.get('app_name') or app_dir.name}.app_icon"
    filename = str(icon_ref).split(".")[-1]
    icon_path = app_dir / "resource" / "icon" / f"{filename}.svg"
    if icon_path.is_file():
        return str(icon_path)
    # 回退：按基座内置图标名解析
    return str(icon_ref)


def _import_app_module(module_name: str, file_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载应用模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register_app(app_dir: Path, registry=None) -> AppContext | None:
    """注册单个应用：解析清单 -> 注册菜单插件 -> 装载页面协议 -> 注册页面插件。

    返回 AppContext（应用无页面入口时仍注册菜单并返回上下文）。
    """
    registry = registry or get_plugin_registry()
    config = load_app_manifest(app_dir)
    name = config.get("app_name") or app_dir.name
    button_id = config.get("button_id") or f"app_{name}"
    page_object = config.get("page_object") or f"{name}Page"
    target = config.get("app_target") or "LeftMenu"
    text_key = config.get("app_text") or f"language.app.{name}.app_text"
    tooltip_key = config.get("app_tooltip") or f"language.app.{name}.app_tooltip"
    icon_path = _resolve_icon(config, app_dir)

    registry.register_menu(
        MenuPlugin(
            plugin_id=config.get("app_id") or f"app.menu.{target.lower()}.{name}",
            target=target,
            item={
                "btn_icon": icon_path,
                "btn_id": button_id,
                "btn_text": text_key,
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
        icon_path=Path(icon_path) if Path(icon_path).is_file() else Path(),
        language=AppSettings.language,
    )

    main_py = app_dir / "gui" / "main.py"
    if not main_py.is_file():
        Logger.warning(f"应用缺少页面实现: {name} (gui/main.py)")
        return context

    module = _import_app_module(f"apps.{name}.gui.main", main_py)

    # 协议 1：register_plugins(registry, app) —— 完全自由
    if callable(getattr(module, "register_plugins", None)):
        module.register_plugins(registry, context)
        Logger.info(f"应用注册完成: {name} (register_plugins)")
        return context

    # 协议 2：PAGE（含 load_page(window) 方法）
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
            )
        )
        return context

    # 协议 3：build_page(app) -> QWidget
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
            )
        )
        return context

    Logger.warning(f"应用缺少页面入口: {name} (需导出 PAGE / build_page / register_plugins)")
    return context


def load_apps(root: str | Path | None = None, force: bool = False) -> list[Path]:
    """发现并注册全部应用（幂等：重复调用直接返回缓存），返回应用目录列表。

    - 单个应用加载失败不影响其余应用；
    - 完成后注入当前语言的全部应用语言包。
    """
    global _APP_DIRS, _LOADED
    if _LOADED and not force:
        return _APP_DIRS

    app_dirs = discover_app_dirs(root)
    _APP_DIRS = app_dirs

    registry = get_plugin_registry()
    loaded = 0
    for app_dir in app_dirs:
        try:
            register_app(app_dir, registry=registry)
            loaded += 1
        except Exception as exc:
            Logger.error(f"应用加载失败: {app_dir.name}: {exc}")
            record_event(
                "app.load_error",
                category="app",
                level="error",
                payload={"app": app_dir.name, "error": str(exc)},
            )

    apply_apps_language(AppSettings.language, app_dirs)
    _LOADED = True
    Logger.info(f"应用加载完成: {loaded}/{len(app_dirs)}")
    record_event("apps.loaded", category="app", payload={"total": len(app_dirs), "loaded": loaded})
    return app_dirs


def reset_apps_cache() -> None:
    """重置加载标记（测试/热重载场景使用）。"""
    global _LOADED, _APP_DIRS
    _LOADED = False
    _APP_DIRS = []
