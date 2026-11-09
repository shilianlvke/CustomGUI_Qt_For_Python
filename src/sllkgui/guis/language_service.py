"""语言切换服务：整体切换语言（委托 LanguageManager）并刷新窗口级 UI。

切换流程：
1. ``Language.apply(lang)`` —— 重装基座语言包 + 注入全部 App 语言，
   并广播通知（左菜单/标题栏/左列等组件订阅后自动刷新文本与提示）；
2. 窗口级刷新：窗口标题、当前页标题；
3. **页面刷新（两条路径）**：
   - 局部刷新：先跳过 ``Main_Page`` / ``widget_show`` 两个占位 QWidget，
     栈内**所有真实页面**都提供可调用的 ``retranslate()``（无参）或
     ``retranslateUi()``（按签名适配）时逐个重翻译，直接刷新标题，
     不重建页面栈（保留页面内状态与滚动位置）；
   - 整页重建：任一真实页面缺少重翻译方法或调用失败、或跳过占位页后
     没有任何真实页面时，清空页面容器并重新加载全部页面；重建前捕获
     所有 ``QScrollArea`` 的滚动位置，重建后按稳定键恢复，减少状态丢失；
   - 基座内置预览页未提供 ``retranslate()``，故默认仍走整页重建；局部刷新
     只对实现了 ``retranslate()`` / ``retranslateUi()`` 的第三方页面生效；
4. **刷新成功**才把目标语言写入用户配置覆盖层
   （``<data_root>/settings/user.yaml``），下次启动由
   ``SetupMainWindow.restore_ui_state`` 读取；**刷新失败**则回滚到切换前的
   语言、记录 warning、不写 ``user.yaml``，并返回旧语言名（不抛异常）。
"""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QWidget

from sllkgui.appcore import LANGUAGE_OPTIONS, Language, Logger, save_user_settings

from .windows.main_window.functions import MainFunctions

#: 内置占位页（uic 生成的容器 QWidget），不是应用页面、永远不提供重翻译方法
_PLACEHOLDER_PAGES = frozenset({"Main_Page", "widget_show"})


def current_language() -> str:
    """返回当前激活语言。"""
    return Language.current()


def available_languages() -> tuple[str, ...]:
    return LANGUAGE_OPTIONS


def apply_language(language: str, window=None) -> str:
    """整体切换到指定语言并刷新 UI，返回新语言名（失败时返回旧语言名）。

    页面刷新有两条路径（见模块顶部说明）：

    - **局部刷新**：跳过占位页后，栈内所有真实页面都实现 ``retranslate()``
      或 ``retranslateUi()`` 时逐个调用，只刷新窗口标题与当前页标题，
      页面实例与滚动状态保持不变；基座内置预览页未提供这两个方法，
      默认走整页重建，局部刷新只对第三方页面生效；
    - **整页重建**：任一真实页面缺少可调用的重翻译方法或调用失败时回退到
      重建页面栈；重建前记录各 ``QScrollArea`` 的滚动位置并在重建后恢复。

    窗口级刷新抛异常时回滚 ``Language.apply(previous)``、记录 warning、
    **不写 user.yaml**，并返回 ``previous``（不抛异常）；成功时才通知 v2
    插件的 ``on_language_changed`` 并持久化选择。
    """
    previous = Language.current()
    # 1. 状态 + 广播（组件自刷新）
    Language.apply(language)
    # 2. 窗口级刷新（标题 + 页面局部刷新或整页重建）；失败则回滚且不落盘
    if window is not None:
        try:
            _refresh_window(window)
        except Exception as exc:
            Logger.warning(f"语言刷新失败，回滚到 {previous}: {exc}")
            Language.apply(previous)
            return previous
    # 3. 成功分支：通知 v2 插件，再记住用户选择
    _notify_plugins_language_changed(language)
    save_user_settings(language=language)
    return language


def _notify_plugins_language_changed(language: str) -> None:
    """语言切换成功后通知所有 v2 插件；单个钩子异常被隔离，不影响切换。

    延迟导入 ``app_state`` 避免加载器与语言服务之间的循环 import。
    """
    from . import app_state

    for handle in app_state.handles:
        plugin = handle.plugin
        if plugin is None:
            continue
        try:
            plugin.on_language_changed(language)
        except Exception as exc:
            Logger.warning(f"应用 on_language_changed 失败: {handle.name}: {exc}")


def switch_language(window=None) -> str:
    """在可用语言间循环切换，返回新语言名。

    仅作为宿主脚本/自定义按钮的程序化助手；基座标题栏不再提供循环切换，
    外观配置抽屉由用户直接选择目标语言。
    """
    options = available_languages()
    try:
        index = options.index(current_language())
    except ValueError:
        index = -1
    target = options[(index + 1) % len(options)]
    return apply_language(target, window=window)


def _refresh_window(window) -> None:
    ui = getattr(window, "ui", None)
    if ui is None:
        return

    if callable(getattr(window, "setWindowTitle", None)):
        window.setWindowTitle(Language.custom_ui.sys_name)

    if not _retranslate_pages(window):
        _rebuild_pages(window)
    _refresh_current_page_title(window)


def _page_stack(window):
    return getattr(getattr(window.ui, "load_pages", None), "pages", None)


def _call_retranslate_ui(page, handler) -> bool:
    """按签名安全调用 uic 生成的 ``retranslateUi``。

    uic 生成的方法通常带一个参数（传页面自身）；若它是无参形式，
    ``handler(page)`` 会抛 ``TypeError``，此时退回 ``handler()``。
    其它异常或两种形式都失败时返回 False，由调用方回退整页重建。
    """
    try:
        try:
            handler(page)
        except TypeError:
            handler()
    except Exception as exc:
        Logger.debug(f"页面 retranslateUi 失败，回退整页重建: {exc}")
        return False
    return True


def _retranslate_pages(window) -> bool:
    """尝试页面局部刷新：所有真实页面都能重翻译时返回 True。

    跳过 objectName 为 ``Main_Page`` / ``widget_show`` 的占位 QWidget；先确认
    每个真实页面都提供可调用的 ``retranslate()``（无参）或 ``retranslateUi()``
    （按签名适配）再逐个调用，避免只刷新一半就中断；缺失方法或调用失败都返回
    False，由调用方回退整页重建。跳过占位页后栈里没有真实页面时同样返回
    False，保持整页重建语义。
    """
    pages = _page_stack(window)
    if pages is None:
        return False
    count = pages.count()
    if count <= 0:
        return False

    targets: list[tuple[object, object, bool]] = []
    for index in range(count):
        page = pages.widget(index)
        if page.objectName() in _PLACEHOLDER_PAGES:
            continue
        retranslate = getattr(page, "retranslate", None)
        if callable(retranslate):
            targets.append((page, retranslate, False))
            continue
        retranslate_ui = getattr(page, "retranslateUi", None)
        if callable(retranslate_ui):
            targets.append((page, retranslate_ui, True))
            continue
        return False

    if not targets:
        return False

    for page, handler, is_retranslate_ui in targets:
        try:
            if is_retranslate_ui:
                ok = _call_retranslate_ui(page, handler)
            else:
                handler()
                ok = True
        except Exception as exc:
            Logger.debug(f"页面重翻译失败，回退整页重建: {exc}")
            return False
        if not ok:
            return False
    return True


def _owning_page(widget, pages):
    """向上寻找直接挂在页面栈上的页面容器；不在栈内返回 ``None``。"""
    node = widget
    try:
        parent = node.parentWidget()
        while parent is not None and parent is not pages:
            node = parent
            parent = node.parentWidget()
    except RuntimeError:  # C++ 对象已销毁
        return None
    return node if parent is pages else None


def _scroll_key(page, area, counters) -> tuple[str, str, int]:
    """滚动区稳定键：页面 objectName + 滚动区 objectName（缺失时用类型）+ 同名序号。"""
    page_name = page.objectName()
    area_name = area.objectName() or type(area).__name__
    group = (page_name, area_name)
    index = counters.get(group, 0)
    counters[group] = index + 1
    return (page_name, area_name, index)


def _capture_scroll_positions(pages) -> dict[tuple[str, str, int], tuple[int, int]]:
    """记录页面栈内所有 ``QScrollArea`` 的（水平, 垂直）滚动位置。"""
    positions: dict[tuple[str, str, int], tuple[int, int]] = {}
    if pages is None:
        return positions
    counters: dict[tuple[str, str], int] = {}
    try:
        areas = pages.findChildren(QScrollArea)
    except RuntimeError:
        return positions
    for area in areas:
        try:
            page = _owning_page(area, pages)
            if page is None:
                continue
            key = _scroll_key(page, area, counters)
            positions[key] = (
                area.horizontalScrollBar().value(),
                area.verticalScrollBar().value(),
            )
        except RuntimeError:
            continue
    return positions


def _restore_scroll_positions(pages, positions) -> None:
    """按稳定键恢复滚动位置；跳过不可见或尚未布局的控件。"""
    if pages is None or not positions:
        return
    counters: dict[tuple[str, str], int] = {}
    try:
        areas = pages.findChildren(QScrollArea)
    except RuntimeError:
        return
    for area in areas:
        try:
            page = _owning_page(area, pages)
            if page is None:
                continue
            key = _scroll_key(page, area, counters)
            value = positions.get(key)
            if value is None:
                continue
            viewport = area.viewport()
            if not area.isVisible() or viewport.width() <= 0 or viewport.height() <= 0:
                continue
            area.horizontalScrollBar().setValue(value[0])
            area.verticalScrollBar().setValue(value[1])
        except RuntimeError:
            continue


def _rebuild_pages(window) -> None:
    """清空并重新加载全部页面，使页面内文本随语言切换而更新。

    拆除页面前先捕获滚动位置，重建并按稳定键恢复，避免语言切换后用户
    原来滚动到的位置被重置到顶部。宿主没有页面栈时（如无 UI 的桩窗口）
    直接跳过：没有可重建的页面，不应被当成刷新失败而回滚语言切换。
    """
    ui = getattr(window, "ui", None)
    load_pages = getattr(ui, "load_pages", None)
    pages = getattr(load_pages, "pages", None)
    if pages is None:
        return
    left_menu = getattr(ui, "left_menu", None)
    current_btn = left_menu.active_button_id() if callable(getattr(left_menu, "active_button_id", None)) else None
    scroll_positions = _capture_scroll_positions(pages)

    # A combo/menu popup can survive its parent page briefly and emit
    # currentIndexChanged after the C++ widget was deleted.  Close popups
    # before tearing the page down.
    from PySide6.QtWidgets import QApplication

    popup = QApplication.activePopupWidget()
    if popup is not None:
        popup.close()

    # 移除全部已加载页面（setParent(None) 使其立即脱离对象树，避免 findChild 命中旧页面）
    while pages.count():
        widget = pages.widget(0)
        pages.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()

    from .windows.main_window.registry import (
        ensure_registered_page,
        get_default_page_object,
        get_page_routes,
        load_registered_pages,
    )

    load_registered_pages(window, eager=False)

    routes = get_page_routes(Language)
    target = routes.get(current_btn)
    page_object = target[0] if target else get_default_page_object()
    ensure_registered_page(window, page_object)

    page = pages.findChild(QWidget, page_object)
    if page is None and pages.count():
        page = pages.currentWidget()
    if page is not None:
        # 页面刚整体重建，旧页已脱离对象树：不做切换过场，避免抓到空白遮罩
        MainFunctions.set_page(window, page, animate=False)
    _restore_scroll_positions(pages, scroll_positions)
    Logger.debug(f"页面重建完成: {pages.count()} 个页面（当前 {page_object}）")


def _refresh_current_page_title(window) -> None:
    """按当前激活按钮重新解析页面标题。"""
    title_bar = getattr(window.ui, "title_bar", None)
    left_menu = getattr(window.ui, "left_menu", None)
    if title_bar is None or left_menu is None:
        return
    if not callable(getattr(left_menu, "active_button_id", None)):
        return

    from .windows.main_window.registry import get_page_routes

    routes = get_page_routes(Language)
    active_id = left_menu.active_button_id()
    if active_id and active_id in routes:
        title_bar.set_title(routes[active_id][1])
