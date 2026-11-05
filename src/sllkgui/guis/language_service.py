"""语言切换服务：整体切换语言（委托 LanguageManager）并刷新窗口级 UI。

切换流程：
1. ``Language.apply(lang)`` —— 重装基座语言包 + 注入全部 App 语言，
   并广播通知（左菜单/标题栏/左列等组件订阅后自动刷新文本与提示）；
2. 窗口级刷新：窗口标题、当前页标题；
3. **页面刷新（两条路径）**：
   - 局部刷新：若页面栈中**所有已加载页面**都提供可调用的 ``retranslate()``，
     逐个调用后直接刷新标题，不重建页面栈（保留页面内状态与滚动位置）；
   - 整页重建：任一页面缺少 ``retranslate()`` 或调用失败时，清空页面容器
     并重新加载全部页面，使页面内文本完整切换；重建前捕获所有
     ``QScrollArea`` 的滚动位置，重建后按稳定键恢复，减少状态丢失；
4. 目标语言写入用户配置覆盖层（``<data_root>/settings/user.yaml``），
   下次启动由 ``SetupMainWindow.restore_ui_state`` 读取。
"""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QWidget

from sllkgui.appcore import LANGUAGE_OPTIONS, Language, Logger, save_user_settings

from .windows.main_window.functions import MainFunctions


def current_language() -> str:
    """返回当前激活语言。"""
    return Language.current()


def available_languages() -> tuple[str, ...]:
    return LANGUAGE_OPTIONS


def apply_language(language: str, window=None) -> str:
    """整体切换到指定语言并刷新 UI，返回新语言名。

    页面刷新有两条路径（见模块顶部说明）：

    - **局部刷新**：页面栈中所有已加载页面都实现 ``retranslate()`` 时逐个
      调用，只刷新窗口标题与当前页标题，页面实例与滚动状态保持不变；
    - **整页重建**：任一页面缺少 ``retranslate()`` 或调用失败时回退到重建
      页面栈；重建前记录各 ``QScrollArea`` 的滚动位置并在重建后恢复。
    """
    # 1. 状态 + 广播（组件自刷新）
    Language.apply(language)
    # 2. 窗口级刷新（标题 + 页面局部刷新或整页重建）
    if window is not None:
        try:
            _refresh_window(window)
        except Exception as exc:
            Logger.warning(f"语言刷新部分失败: {exc}")
    # 3. 记住用户选择，下次启动由 SetupMainWindow.restore_ui_state 恢复
    save_user_settings(language=language)
    return language


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


def _retranslate_pages(window) -> bool:
    """尝试页面局部刷新：全部已加载页面都实现 ``retranslate()`` 时返回 True。

    先确认所有页面都提供可调用的 ``retranslate()`` 再逐个调用，避免只刷新
    一半就中断；任一页面缺失或调用抛异常都返回 False，由调用方回退整页重建。
    """
    pages = _page_stack(window)
    if pages is None:
        return False
    count = pages.count()
    if count <= 0:
        return False

    handlers = []
    for index in range(count):
        page = pages.widget(index)
        handler = getattr(page, "retranslate", None)
        if not callable(handler):
            return False
        handlers.append(handler)

    for handler in handlers:
        try:
            handler()
        except Exception as exc:
            Logger.debug(f"页面 retranslate 失败，回退整页重建: {exc}")
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
    原来滚动到的位置被重置到顶部。
    """
    pages = window.ui.load_pages.pages
    left_menu = getattr(window.ui, "left_menu", None)
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
