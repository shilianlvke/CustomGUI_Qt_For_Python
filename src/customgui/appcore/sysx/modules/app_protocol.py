"""应用插件协议 v2：面向对象的应用入口。

为什么要新增 v2
---------------
v1 有三套页面协议（``register_plugins`` / ``PAGE`` / ``build_page``），语义
互相不一致，同一个问题在不同协议里有不同答案：

=====================  ====================  ==================  ==================
问题                    register_plugins           PAGE              build_page
=====================  ====================  ==================  ==================
``self`` 是谁           自由决定              页面类实例           无 self
页面由谁入栈            应用自己 addWidget    基座                基座
能否拿到 AppContext     能（第二参数）         **不能**            能
多页面                 能                     单页面               单页面
=====================  ====================  ==================  ==================

v2 把这些歧义一次性收敛：``AppPlugin`` 实例自己就是应用的代表，
``pages()`` 返回声明式的 ``AppPage`` 列表，**入栈由基座负责**，
``AppPage.build(ctx, window)`` 两个参数永远都在。

v1 保持逐字节兼容——``register_plugins`` / ``PAGE`` / ``build_page`` 的
既有应用一行都不用改，加载器内部自动适配。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# 注意：这里**不能** import customgui.guis.app_loader。
# appcore 是最底层，依赖它会造成层级倒挂（有架构边界测试守着）。
# 因此 AppContext 的类型标注写成字符串，运行时只当鸭子类型用。

#: 本模块实现的协议版本号，写入清单的 ``protocol`` 字段。
PROTOCOL_VERSION = "2"
#: 仍然受支持的历史版本（v1 三套函数式协议）。
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"1", "2"})


class AppPluginError(RuntimeError):
    """应用插件声明有误（清单与代码不一致、缺少逻辑层等）。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


@dataclass
class AppPage:
    """一个页面声明（v2 协议）。

    ``build`` 签名为 ``build(ctx, window) -> QWidget``：

    - ``ctx``：:class:`~customgui.guis.app_loader.AppContext`，永远提供，
      不需要应用去猜从哪里取；
    - ``window``：主窗口对象，需要自己往容器里塞控件时用；
    - 返回值：页面控件。**基座负责** ``setObjectName`` 与 ``addWidget``，
      应用不要自己入栈——这正是 v1 里 ``register_plugins`` 最容易写错的
      地方（漏入栈页面就永远不显示，且没有任何报错）。
    """

    button_id: str
    page_object: str
    build: Callable[..., Any]
    title: str | Callable[[Any], str] | None = None
    icon: str | None = None
    tooltip: str | Callable[[Any], str] | None = None
    default: bool = False
    show_top: bool = True
    is_active: bool = False
    #: 页面语言键；为 ``None`` 时由 ``button_id`` 与 ``page_object`` 推导
    title_key: str | None = None

    def resolve_title(self, language: Any, fallback: str = "") -> str:
        """解析页面标题：支持直接给字符串、给语言键、给 ``fn(language)``。"""
        if callable(self.title):
            try:
                return str(self.title(language))
            except Exception:
                return fallback
        if self.title:
            return str(language.resolve_key(self.title, self.title))
        if self.title_key:
            return str(language.resolve_key(self.title_key, fallback or self.title_key))
        return fallback

    def resolve_tooltip(self, language: Any, fallback: str = "") -> str:
        if callable(self.tooltip):
            try:
                return str(self.tooltip(language))
            except Exception:
                return fallback
        if self.tooltip:
            return str(language.resolve_key(self.tooltip, self.tooltip))
        return fallback


@dataclass
class AppPlugin:
    """应用插件基类（v2 协议）。

    最小实现只需覆写 :meth:`pages`::

        class MyApp(AppPlugin):
            def pages(self) -> list[AppPage]:
                return [
                    AppPage("btn_home", "pageHome", build_home,
                            title_key="language.app.myapp.nav_home", default=True),
                ]

    需要初始化逻辑时覆写 :meth:`on_load`——它在**所有页面构建之前**调用一次，
    此时 ``self.ctx`` 已就绪::

        def on_load(self, ctx):
            self.hub = LauncherHub.instance()
    """

    #: 由加载器注入，不要求子类自己声明
    ctx: Any = field(default=None, init=False, repr=False)
    #: 应用名（= 清单 ``app_name``，缺省为目录名）
    name: str = field(default="", init=False)
    #: 应用目录
    app_dir: Any = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def on_load(self, ctx: Any) -> None:
        """应用加载完成、页面尚未构建时的钩子。默认不做任何事。"""

    def on_language_changed(self, language: str) -> None:
        """语言切换后的钩子。默认不做任何事。

        大多数应用不需要覆写——页面标题由基座通过 ``title`` 声明自动刷新；
        只有当应用在 ``build`` 之外持有需要手动改文案的控件时才用得上。
        """

    def on_unload(self) -> None:
        """应用卸载前的钩子。默认不做任何事。"""

    # ------------------------------------------------------------------
    # 页面声明
    # ------------------------------------------------------------------
    def pages(self) -> list[AppPage]:
        """返回页面声明列表。基类返回空列表。"""
        return []

    # ------------------------------------------------------------------
    # 内部：由加载器调用
    # ------------------------------------------------------------------
    def _bind(self, ctx: Any) -> None:
        self.ctx = ctx
        self.name = ctx.name
        self.app_dir = ctx.app_dir


__all__ = [
    "PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "AppPage",
    "AppPlugin",
    "AppPluginError",
]
