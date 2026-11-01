"""Apps 应用模组加载器：从 ``Apps/`` 目录发现并挂载应用。

应用模组协议（每个 ``Apps/<app_name>/`` 是一个自包含模组）::

    Apps/<app_name>/
    ├── config.yml               # 应用清单（app_name/protocol/core/button_id/...）
    ├── app.py                   # 可选：v2 插件入口（导出 AppPlugin 子类）
    ├── resource/                # 应用私有资产（图标、应用菜单文案）
    │   ├── icon/app_icon.svg
    │   └── lang/{zh_cn,en_us}.yml
    ├── brand/customui/          # 可选：品牌覆盖层（主题/语言/图标）
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
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from customgui.appcore import (
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    AppPage,
    AppPlugin,
    AppPluginError,
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

# 应用模组的模块命名空间。
#
# ``apps/`` 是**目录插件**，不在 ``sys.path`` 里，因此不能用真正的包路径导入。
# 这里用一个私有命名空间伪造父包（下划线前缀，明确「非公开契约」），
# 消费方不应依赖这个名字，而应使用 ``load_apps()`` 返回的 ``AppHandle``。
_APP_NAMESPACE = "_customgui_apps"

# 已发现的应用目录缓存（语言切换时复用）
_APP_DIRS: list[Path] = []
# 全局加载标记（load_apps 幂等）
_LOADED = False


@dataclass
class AppContext:
    """传递给应用页面代码的上下文。

    - 清单：``config``（config.yml 全部字段）；
    - 语言：``lang_text(key)``（应用内 language 命名空间）；
    - 资源：``resource(*parts)`` / ``icon(name)`` / ``image(name)`` /
      ``voice(name)`` / ``lang_file(lang)`` —— 全部解析到应用内
      ``resource/`` 目录，插件自包含、与基座资源互不干扰；
    - 品牌覆盖层：``brand()`` —— 应用自带主题/语言/图标的根目录
      （其下直接是 ``customui/``），基座会自动纳入资源解析链；
    - 目录：``app_dir``（应用根目录）、``core_dir``（逻辑层目录）、
      ``icon_path``（默认图标，没有则为 ``None``）；
    - 模块：``import_module("pages.home")`` —— 在应用命名空间内导入，
      不需要调用方拼 ``_customgui_apps.<name>.`` 前缀。
    """

    name: str
    app_dir: Path
    config: Attrs
    icon_path: Path | None = None
    #: 当前语言名，``None`` 表示跟随全局（每次读取都取最新值）
    _language: str | None = None
    #: 应用入口模块名（``_customgui_apps.<name>.app`` 或
    #: ``_customgui_apps.<name>.gui.main``），用于内部导入与句柄定位
    module_name: str | None = None
    #: 逻辑层目录名（清单 ``core`` 字段），如 ``launchercore``
    core_name: str | None = None

    @property
    def language(self) -> str:
        """当前语言。**每次读取都取最新值**，不要缓存到应用侧。"""
        if self._language:
            return self._language
        return AppSettings.language

    @language.setter
    def language(self, value: str) -> None:
        self._language = value

    # ------------------------------------------------------------------
    # 语言
    # ------------------------------------------------------------------
    def lang_text(self, key: str, default: Any = None) -> Any:
        """从本应用语言命名空间读取文本，如 ``lang_text("app_text")``。"""
        return Language.resolve(f"app.{self.name}.{key}", default)

    # ------------------------------------------------------------------
    # 资源（应用内 resource/ 目录，插件自包含）
    # ------------------------------------------------------------------
    def resource(self, *parts: str) -> Path:
        """应用内资源路径：``resource("images", "a.png")`` -> ``<app>/resource/images/a.png``。"""
        return self.app_dir.joinpath("resource", *parts)

    def brand(self, *parts: str) -> Path:
        """品牌覆盖层路径：``brand("customui", "themes")``。

        其下直接是 ``customui/``，基座会自动把它纳入资源解析链（见
        ``appcore.sysx.config.paths._app_overlay_roots``）。
        """
        return self.app_dir.joinpath("brand", *parts)

    def icon(self, name: str) -> Path:
        return self.resource("icon", name)

    def image(self, name: str) -> Path:
        return self.resource("images", name)

    def voice(self, name: str) -> Path:
        return self.resource("voice", name)

    def lang_file(self, language: str | None = None) -> Path:
        return self.resource("lang", f"{language or self.language}.yml")

    # ------------------------------------------------------------------
    # 逻辑层
    # ------------------------------------------------------------------
    @property
    def core_dir(self) -> Path | None:
        """逻辑层目录（清单 ``core`` 声明），未声明或不存在时为 ``None``。"""
        if not self.core_name:
            return None
        candidate = self.app_dir / self.core_name
        return candidate if candidate.is_dir() else None

    def import_module(self, relative: str) -> ModuleType:
        """在**本应用命名空间内**导入模块。

        ``ctx.import_module("pages.home")`` 等价于
        ``import _customgui_apps.<name>.pages.home``，但不需要调用方知道
        那个私有命名空间的存在。

        用 ``self.name`` 拼模块名而不是从 ``module_name`` 反推：入口可能是
        ``gui/main.py`` 或 ``app.py``，两种布局下应用包名都是
        ``_customgui_apps.<name>``，与入口文件位置无关。
        """
        return importlib.import_module(f"{_APP_NAMESPACE}.{self.name}.{relative}")


@dataclass
class AppHandle:
    """已加载应用的句柄：消费方按**名字**取模块，不再猜模块路径。

    模块在 ``_customgui_apps.<name>...`` 这个**私有**命名空间下（不在
    ``sys.path`` 里的目录插件只能这样导入），所以名字对消费方是透明的：

    .. code-block:: python

        handles = {handle.name: handle for handle in load_apps()}
        hub = handles["pycl2"].module.hub.LauncherHub.instance()

    ``module`` 在应用没有 ``app.py`` 也没有 ``gui/main.py`` 时为 ``None``。
    """

    name: str
    module: ModuleType | None
    context: AppContext
    source: str = "path"
    #: v2 协议下应用暴露的 ``AppPlugin`` 实例（v1 应用为 ``None``）
    plugin: AppPlugin | None = None


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
    Language.app = collect_app_languages(language, app_dirs)
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


def _ensure_parent_packages(module_name: str, app_dir: Path) -> None:
    """为应用主模块建立父包层级，使 App 内部相对导入可用。

    例：加载 ``_customgui_apps.example.gui.main`` 时建立：

    - ``_customgui_apps``：__path__ = Apps 根目录，并安装一个只在该命名空间内
      生效的 MetaPathFinder，负责把 ``<app>/xxx`` 目录按包加载；
    - ``_customgui_apps.example``：__path__ = 应用目录（由此支持
      ``from .lib import ...`` 等自定义逻辑目录的常规导入）；
    - ``_customgui_apps.example.gui``：__path__ = gui 子目录。

    应用内的子模块（如 ``lib/__init__.py``）由 Python 常规导入机制按
    ``__path__`` 自动发现；跨目录的相对导入（``lib/__init__.py`` 里的
    ``from ..calc import add``）则需要 Finder 才能定位到 ``<app>/calc.py``。
    """
    parts = module_name.split(".")
    app_name = parts[1]
    # key 必须与模块名一致（只用 app_name），否则 Finder 查不到根目录、
    # 应用内部的跨目录相对导入会静默失效。清单校验保证 app_name == 目录名，
    # 这里再按模块名兜一次底。
    _NAMESPACE_ROOTS[app_name] = str(app_dir)
    _install_namespace_finder()

    for index in range(len(parts) - 1):
        package_name = ".".join(parts[: index + 1])
        # 已存在的包也需更新 __path__（同名 App 目录可能变化，如测试注入）
        package = sys.modules.get(package_name) or types.ModuleType(package_name)
        if index == 0:
            # 命名空间根 -> Apps 根目录
            package.__path__ = [str(apps_root())]
        elif index == 1:
            # <ns>.<app_name> -> 应用目录
            package.__path__ = [str(app_dir)]
        else:
            # <ns>.<app_name>.<子包> -> 应用内同名子目录
            sub_dir = app_dir.joinpath(*parts[2 : index + 1])
            package.__path__ = [str(sub_dir)]
        sys.modules[package_name] = package

    # 确保模块名中的应用名与目录名一致（防御：加载器始终按目录名生成）
    if parts[1] != app_name:
        Logger.warning(f"应用模块名与目录名不一致: {module_name} vs {app_dir.name}")


_NAMESPACE_ROOTS: dict[str, str] = {}


def _install_namespace_finder() -> None:
    """安装伪命名空间 Finder（全局唯一）。"""
    if not any(isinstance(finder, _NamespacePackageFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _NamespacePackageFinder())


class _NamespacePackageFinder:
    """把 ``<ns>.<app>.<任何层级>`` 解析成该应用目录下的真实包/模块。

    ``sys.modules`` 只预置了 ``gui`` 这一条链路，应用里其余目录（``lib``、
    ``LauncherCore`` 等）必须由 Finder 兜住，否则应用内部的跨目录相对导入
    （``from ..calc import add``）会找不到模块。

    每个应用名对应的根目录单独登记，避免多个 Apps 根（仓库 demo 与
    用户目录）互相串台。
    """

    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001 - importlib 协议
        if not fullname.startswith(f"{_APP_NAMESPACE}."):
            return None
        parts = fullname[len(_APP_NAMESPACE) + 1 :].split(".")
        if len(parts) < 2:
            return None
        root = _NAMESPACE_ROOTS.get(parts[0])
        if root is None:
            return None
        candidate = Path(root).joinpath(*parts[1:])
        if candidate.is_dir():
            init = candidate / "__init__.py"
            return importlib.util.spec_from_file_location(
                fullname,
                init,
                submodule_search_locations=[str(candidate)],
            )
        module_file = candidate.with_suffix(".py")
        if module_file.is_file():
            return importlib.util.spec_from_file_location(fullname, module_file)
        return None


def _import_app_module(module_name: str, app_dir: Path, file_path: Path) -> ModuleType:
    _ensure_parent_packages(module_name, app_dir)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载应用模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _manifest_protocol(config: Attrs) -> str:
    """读清单声明的协议版本，缺省视为 v1（历史应用无此字段）。"""
    raw = config.get("protocol")
    version = str(raw).strip() if raw is not None else "1"
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise AppPluginError(
            "APP_PROTOCOL_UNSUPPORTED",
            f"清单 protocol={version!r} 不受支持（可用: {sorted(SUPPORTED_PROTOCOL_VERSIONS)}）",
        )
    return version


def _resolve_entry(protocol: str, app_dir: Path, name: str) -> tuple[Path | None, str]:
    """解析应用的入口文件与对应模块名。

    返回 ``(file_path, module_name)``；找不到入口时返回 ``(None, "")``。

    - **v2**：优先 ``app.py``（应用根，插件入口），回退 ``gui/main.py``；
    - **v1**：``gui/main.py``（历史布局，保持兼容）。
    """
    candidates: list[tuple[Path, str]] = []
    if protocol == PROTOCOL_VERSION:
        candidates.append((app_dir / "app.py", f"{_APP_NAMESPACE}.{name}.app"))
    candidates.append((app_dir / "gui" / "main.py", f"{_APP_NAMESPACE}.{name}.gui.main"))
    for file_path, module_name in candidates:
        if file_path.is_file():
            return file_path, module_name
    return None, ""


def _check_core(config: Attrs, app_dir: Path) -> str | None:
    """校验清单 ``core`` 声明的逻辑层目录存在，返回目录名。"""
    raw = config.get("core")
    if raw is None:
        return None
    core_name = str(raw).strip()
    if not core_name:
        return None
    if not (app_dir / core_name).is_dir():
        raise AppPluginError(
            "APP_CORE_MISSING",
            f"清单声明 core={core_name!r}，但目录不存在: {app_dir / core_name}",
        )
    return core_name


def _check_name(config: Attrs, app_dir: Path) -> str:
    """清单 ``app_name`` 必须与目录名一致。

    不一致时命名空间 Finder 会用目录名登记、而模块名用 ``app_name``，
    导致应用内部 ``import`` 静默失效——宁可这里显式报错。
    """
    name = str(config.get("app_name") or app_dir.name).strip()
    if name != app_dir.name:
        raise AppPluginError(
            "APP_NAME_MISMATCH",
            f"清单 app_name={name!r} 与目录名 {app_dir.name!r} 不一致（会让应用内导入失效）",
        )
    return name


def _instantiate_plugin(module: ModuleType, config: Attrs) -> AppPlugin | None:
    """从应用入口模块（``app.py`` 或 ``gui/main.py``）里找出 v2 插件实例。

    支持三种写法，优先级从高到低：

    1. 模块级 ``PLUGIN = MyApp()`` —— 显式实例
    2. 模块级 ``PLUGIN = MyApp``   —— 类，加载器负责实例化
    3. 模块内唯一的 ``AppPlugin`` 子类 —— 约定优于配置
    """
    candidate = getattr(module, "PLUGIN", None)
    if candidate is not None:
        if isinstance(candidate, AppPlugin):
            return candidate
        if isinstance(candidate, type) and issubclass(candidate, AppPlugin):
            return candidate()
        raise AppPluginError(
            "APP_PLUGIN_INVALID",
            f"PLUGIN 必须是 AppPlugin 实例或子类，得到 {type(candidate).__name__}",
        )

    declared = str(config.get("plugin") or "").strip()
    if declared:
        target = getattr(module, declared, None)
        if target is None:
            raise AppPluginError("APP_PLUGIN_MISSING", f"清单 plugin={declared!r} 在入口模块中不存在")
        return target() if isinstance(target, type) else target

    subclasses = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and issubclass(value, AppPlugin) and value is not AppPlugin
    ]
    if len(subclasses) == 1:
        return subclasses[0]()
    if len(subclasses) > 1:
        names = ", ".join(sorted(cls.__name__ for cls in subclasses))
        raise AppPluginError(
            "APP_PLUGIN_AMBIGUOUS",
            f"入口模块里发现多个 AppPlugin 子类（{names}），请用 PLUGIN = ... 显式指定",
        )
    return None


def _register_v2_pages(
    plugin: AppPlugin,
    pages: list[AppPage],
    registry,
    context: AppContext,
    config: Attrs,
) -> None:
    """把 ``AppPage`` 声明翻译成基座的菜单 + 页面插件。

    清单里已经声明了主按钮（``button_id``）时，与之同名的页面不再重复
    注册菜单——否则左侧会出现两个入口。
    """
    manifest_button = str(config.get("button_id") or "")
    name = context.name
    for page in pages:
        text_key = page.title_key or f"language.app.{name}.{page.button_id}"
        # ``show_top`` 只决定按钮放顶部还是底部（False 放 bottom_layout），
        # 不决定是否注册菜单——底部按钮（如 settings）同样需要入口。
        if page.button_id != manifest_button:
            registry.register_menu(
                MenuPlugin(
                    plugin_id=f"app.menu.{name}.{page.button_id}",
                    target=str(config.get("app_target") or "LeftMenu"),
                    item={
                        "btn_icon": page.icon or str(config.get("app_icon") or ""),
                        "btn_id": page.button_id,
                        "btn_text": text_key,
                        "btn_tooltip": text_key,
                        "show_top": page.show_top,
                        "is_active": page.is_active,
                    },
                )
            )

        def _loader(window, _page: AppPage = page) -> None:
            widget = _page.build(context, window)
            if widget is None:
                raise AppPluginError(
                    "APP_PAGE_EMPTY",
                    f"应用 {name} 的页面 {_page.page_object} build() 返回了 None",
                )
            widget.setObjectName(_page.page_object)
            window.ui.load_pages.pages.addWidget(widget)

        registry.register_page(
            PagePlugin(
                plugin_id=f"app.page.{name}.{page.page_object}",
                button_id=page.button_id,
                page_object=page.page_object,
                title_getter=lambda language, _page=page, _key=text_key: _page.resolve_title(
                    language, fallback=_key
                ),
                loader=_loader,
                default=page.default,
            )
        )


def register_app(app_dir: Path, registry=None, *, with_handle: bool = False) -> AppContext | AppHandle | None:
    """注册单个应用：解析清单 -> 校验 -> 注册菜单插件 -> 装载页面协议 -> 注册页面插件。

    支持两种协议（由清单 ``protocol`` 字段选择，缺省 ``1``）：

    - **v2**：入口模块导出 ``AppPlugin`` 子类（见 :mod:`app_protocol`）；
    - **v1**：``register_plugins`` / ``PAGE`` / ``build_page`` 三选一（保持原样）。

    返回 AppContext（应用无页面入口时仍注册菜单并返回上下文）。
    """
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


_HANDLES: list[AppHandle] = []


def load_apps(root: str | Path | None = None, force: bool = False) -> list[Path]:
    """发现并注册全部应用（幂等：重复调用直接返回缓存），返回应用目录列表。

    - 单个应用加载失败不影响其余应用；
    - 完成后注入当前语言的全部应用语言包。

    需要按名字取应用模块时用 :func:`load_app_handles`——不要自己拼模块路径，
    应用模块位于私有命名空间下。
    """
    global _APP_DIRS, _LOADED, _HANDLES
    if _LOADED and not force:
        return _APP_DIRS

    app_dirs = discover_app_dirs(root)
    _APP_DIRS = app_dirs

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

    _HANDLES = handles
    apply_apps_language(AppSettings.language, app_dirs)
    _LOADED = True
    Logger.info(f"应用加载完成: {loaded}/{len(app_dirs)}")
    record_event("apps.loaded", category="app", payload={"total": len(app_dirs), "loaded": loaded})
    return app_dirs


def load_app_handles(root: str | Path | None = None, force: bool = False) -> list[AppHandle]:
    """发现并注册全部应用，返回句柄列表（``name`` -> 模块 + 上下文）。

    这是消费方（宿主应用）取自身业务模块的**唯一正路**：
    ``{h.name: h for h in load_app_handles()}``。
    """
    load_apps(root, force=force)
    return list(_HANDLES)


def get_app_handle(name: str, root: str | Path | None = None) -> AppHandle | None:
    """按应用名取句柄；未加载时先加载。找不到返回 ``None``。"""
    load_apps(root)
    for handle in _HANDLES:
        if handle.name == name:
            return handle
    return None


def reset_apps_cache() -> None:
    """重置加载标记（测试/热重载场景使用）。"""
    global _LOADED, _APP_DIRS, _HANDLES
    _LOADED = False
    _APP_DIRS = []
    _HANDLES = []
