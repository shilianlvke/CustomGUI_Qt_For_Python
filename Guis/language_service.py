"""语言切换服务：基座语言包 + 全部应用语言的整体切换与 UI 刷新。

切换流程：
1. ``Language.replace`` 重装基座语言包（避免旧语言残留键）；
2. 注入全部 App 语言（``Language.app.<app_name>``）；
3. 刷新左侧菜单/标题栏按钮文本与提示、窗口标题、当前页标题；
4. 记录日志与遥测事件 ``ui.language_switch``。
"""

from __future__ import annotations

from AppCore import AppLanguages, AppSettings, Language, Logger, record_event

from .app_loader import apply_apps_language

LANGUAGE_OPTIONS = ("zh_cn", "en_us")

_current_language: str | None = None


def current_language() -> str:
    """返回当前激活语言（首次访问时取 AppSettings.language）。"""
    global _current_language
    if _current_language is None:
        _current_language = AppSettings.language
    return _current_language


def available_languages() -> tuple[str, ...]:
    return LANGUAGE_OPTIONS


def apply_language(language: str, window=None) -> str:
    """整体切换到指定语言并刷新 UI，返回新语言名。"""
    global _current_language
    if language not in LANGUAGE_OPTIONS:
        raise ValueError(f"不支持的语言: {language}（可选: {LANGUAGE_OPTIONS}）")

    Language.replace(AppLanguages[language].data)
    apply_apps_language(language)
    _current_language = language
    _refresh_window(window)

    Logger.info(f"语言切换为 {language}")
    record_event("ui.language_switch", category="ui", payload={"language": language})
    return language


def switch_language(window=None) -> str:
    """在可用语言间循环切换，返回新语言名。"""
    target = "en_us" if current_language() == "zh_cn" else "zh_cn"
    return apply_language(target, window=window)


def _refresh_window(window) -> None:
    """刷新窗口上的语言相关 UI（缺省组件时安全跳过）。"""
    if window is None:
        return
    ui = getattr(window, "ui", None)
    if ui is None:
        return

    try:
        left_menu = getattr(ui, "left_menu", None)
        if left_menu is not None and callable(getattr(left_menu, "apply_language", None)):
            left_menu.apply_language(Language.resolve_key)

        title_bar = getattr(ui, "title_bar", None)
        if title_bar is not None and callable(getattr(title_bar, "apply_language", None)):
            title_bar.apply_language(Language.resolve_key)

        if callable(getattr(window, "setWindowTitle", None)):
            window.setWindowTitle(Language.custom_ui.sys_name)

        _refresh_current_page_title(window, title_bar, left_menu)
    except Exception as exc:
        Logger.warning(f"语言刷新部分失败: {exc}")


def _refresh_current_page_title(window, title_bar, left_menu) -> None:
    """按当前激活按钮重新解析页面标题。"""
    if title_bar is None or left_menu is None:
        return
    if not callable(getattr(left_menu, "active_button_id", None)):
        return

    from .windows.main_window.user_define_pages import get_page_routes

    routes = get_page_routes(Language)
    active_id = left_menu.active_button_id()
    if active_id and active_id in routes:
        title_bar.set_title(routes[active_id][1])
