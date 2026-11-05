"""协议 v2 的落地：把 ``AppPlugin.pages()`` 的声明翻译成基座的菜单 + 页面插件。

应用侧只声明「有哪些页面、标题键是什么、要不要默认打开」，**入栈与
``setObjectName`` 由基座负责**，所以这一层是唯一知道 ``PagePlugin`` /
``MenuPlugin`` 细节的地方。
"""

from __future__ import annotations

from types import ModuleType

from sllkgui.appcore import AppPage, AppPlugin, AppPluginError, Attrs, MenuPlugin, PagePlugin

from .app_context import AppContext


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


__all__ = ["_instantiate_plugin", "_register_v2_pages"]
