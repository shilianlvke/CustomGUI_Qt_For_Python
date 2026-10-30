"""语言切换服务：整体切换语言（委托 LanguageManager）并刷新窗口级 UI。

切换流程：
1. ``Language.apply(lang)`` —— 重装基座语言包 + 注入全部 App 语言，
   并广播通知（左菜单/标题栏/左列等组件订阅后自动刷新文本与提示）；
2. 窗口级刷新：窗口标题、当前页标题；
3. **页面重建**：清空页面容器并重新加载全部页面，
   使页面内文本（走语言包的部分）完整切换到新语言。
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from AppCore import LANGUAGE_OPTIONS, Language, Logger

from .windows.main_window.functions import MainFunctions

def current_language() -> str:
    """返回当前激活语言。"""
    return Language.current()


def available_languages() -> tuple[str, ...]:
    return LANGUAGE_OPTIONS


def apply_language(language: str, window=None) -> str:
    """整体切换到指定语言并刷新 UI，返回新语言名。"""
    # 1. 状态 + 广播（组件自刷新）
    Language.apply(language)
    # 2. 窗口级刷新（标题 + 页面重建）
    if window is not None:
        try:
            _refresh_window(window)
        except Exception as exc:
            Logger.warning(f"语言刷新部分失败: {exc}")
    return language


def switch_language(window=None) -> str:
    """在可用语言间循环切换，返回新语言名。"""
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

    _rebuild_pages(window)
    _refresh_current_page_title(window)


def _rebuild_pages(window) -> None:
    """清空并重新加载全部页面，使页面内文本随语言切换而更新。"""
    pages = window.ui.load_pages.pages
    left_menu = getattr(window.ui, "left_menu", None)
    current_btn = left_menu.active_button_id() if callable(getattr(left_menu, "active_button_id", None)) else None

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
