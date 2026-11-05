"""应用侧的两份数据：``AppContext``（传给页面代码）与 ``AppHandle``（回给宿主）。"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from sllkgui.appcore import AppPlugin, AppSettings, Attrs, Language

from .app_namespace import _APP_NAMESPACE


@dataclass
class AppContext:
    """传递给应用页面代码的上下文。

    - 清单：``config``（config.yml 全部字段）；
    - 语言：``lang_text(key)``（应用内 language 命名空间）；
    - 资源：``resource(*parts)`` / ``icon(name)`` / ``image(name)`` /
      ``voice(name)`` / ``lang_file(lang)`` —— 全部解析到应用内
      ``resource/`` 目录，插件自包含、与基座资源互不干扰；
    - 品牌覆盖层：``brand()`` —— 应用自带主题/语言/图标的根目录
      （其下直接是 ``sllkgui/``），基座会自动纳入资源解析链；
    - 目录：``app_dir``（应用根目录）、``core_dir``（逻辑层目录）、
      ``icon_path``（默认图标，没有则为 ``None``）；
    - 模块：``import_module("pages.home")`` —— 在应用命名空间内导入，
      不需要调用方拼 ``_sllkgui_apps.<name>.`` 前缀。
    """

    name: str
    app_dir: Path
    config: Attrs
    icon_path: Path | None = None
    #: 当前语言名，``None`` 表示跟随全局（每次读取都取最新值）
    _language: str | None = None
    #: 应用入口模块名（``_sllkgui_apps.<name>.app`` 或
    #: ``_sllkgui_apps.<name>.gui.main``），用于内部导入与句柄定位
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
        """品牌覆盖层路径：``brand("sllkgui", "themes")``。

        其下直接是 ``sllkgui/``，基座会自动把它纳入资源解析链（见
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
        ``import _sllkgui_apps.<name>.pages.home``，但不需要调用方知道
        那个私有命名空间的存在。

        用 ``self.name`` 拼模块名而不是从 ``module_name`` 反推：入口可能是
        ``gui/main.py`` 或 ``app.py``，两种布局下应用包名都是
        ``_sllkgui_apps.<name>``，与入口文件位置无关。
        """
        return importlib.import_module(f"{_APP_NAMESPACE}.{self.name}.{relative}")


@dataclass
class AppHandle:
    """已加载应用的句柄：消费方按**名字**取模块，不再猜模块路径。

    模块在 ``_sllkgui_apps.<name>...`` 这个**私有**命名空间下（不在
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


__all__ = ["AppContext", "AppHandle"]
