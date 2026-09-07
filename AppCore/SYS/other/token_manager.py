"""令牌管理器。

职责:
- 作为应用上下文的统一入口，持有当前激活的主题、语言、设计令牌快照。
- 提供主题与语言的一键切换，并在切换时广播变更通知。
- 替代原先游离的 ``ColorPalette`` 与 ``Language`` 单例，成为单一事实来源。

设计说明:
- 快照均不可变（主题为 pydantic 冻结模型、令牌为冻结 dataclass）。
- 切换即「换引用 + 派生重建 + 广播」，不产生原地修改。
- 通知机制为纯 Python 观察者，不绑定 Qt，便于测试与分层。
"""

from collections.abc import Callable

from AppCore.SYS.module.token_models import ThemeColors, WindowSettings
from AppCore.SYS.module.token_module import DesignTokens, build_design_tokens
from AppCore.SYS.other.folder_tools import get_app_context, initialize_app_context

EVENT_THEME_CHANGED = "theme_changed"
EVENT_LANGUAGE_CHANGED = "language_changed"

__all__ = [
    "EVENT_LANGUAGE_CHANGED",
    "EVENT_THEME_CHANGED",
    "TokenManager",
    "get_token_manager",
    "initialize_tokens",
]


class TokenManager:
    """应用上下文令牌管理器。"""

    def __init__(self) -> None:
        """初始化令牌管理器。"""
        self._settings: WindowSettings | None = None
        self._theme: ThemeColors | None = None
        self._language: object | None = None
        self._tokens: DesignTokens | None = None
        self._subscribers: dict[str, list[Callable[[], None]]] = {}

    @property
    def settings(self) -> WindowSettings | None:
        """获取窗口设置快照。"""
        return self._settings

    @property
    def theme(self) -> ThemeColors | None:
        """获取当前主题颜色快照。"""
        return self._theme

    @property
    def language(self) -> object | None:
        """获取当前语言包。"""
        return self._language

    @property
    def tokens(self) -> DesignTokens | None:
        """获取派生设计令牌快照。"""
        return self._tokens

    def load(self) -> "TokenManager":
        """加载配置库并产出初始快照。

        返回:
        - TokenManager: 当前实例。
        """
        context = get_app_context()
        self._settings = WindowSettings.model_validate(dict(context.settings))
        self._apply_theme(context.settings.theme_name)
        self._apply_language(context.settings.language)
        return self

    def switch_theme(self, name: str) -> None:
        """切换到指定主题并广播通知。

        参数:
        - name: 主题名。
        """
        self._apply_theme(name)

    def switch_language(self, name: str) -> None:
        """切换到指定语言并广播通知。

        参数:
        - name: 语言名。
        """
        self._apply_language(name)

    def subscribe(self, event: str, callback: Callable[[], None]) -> None:
        """订阅事件通知。

        参数:
        - event: 事件名。
        - callback: 回调函数。
        """
        self._subscribers.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback: Callable[[], None]) -> None:
        """取消订阅事件通知。

        参数:
        - event: 事件名。
        - callback: 已订阅的回调函数。
        """
        callbacks = self._subscribers.get(event)
        if callbacks and callback in callbacks:
            callbacks.remove(callback)

    def _apply_theme(self, name: str) -> None:
        """应用主题并重建派生令牌。"""
        context = get_app_context()
        self._theme = ThemeColors.model_validate(dict(context.themes[name].data.data))
        if self._settings is not None:
            self._tokens = build_design_tokens(self._theme, self._settings)
        self._notify(EVENT_THEME_CHANGED)

    def _apply_language(self, name: str) -> None:
        """应用语言包。"""
        context = get_app_context()
        self._language = context.languages[name].data.data
        self._notify(EVENT_LANGUAGE_CHANGED)

    def _notify(self, event: str) -> None:
        """向订阅者广播事件。"""
        for callback in list(self._subscribers.get(event, [])):
            callback()


_TOKEN_MANAGER: TokenManager | None = None


def get_token_manager(*, reset: bool = False) -> TokenManager:
    """获取全局令牌管理器实例。

    参数:
    - reset: 为 True 时重建并返回新实例。

    返回:
    - TokenManager: 全局令牌管理器。
    """
    state = globals()
    if reset or state["_TOKEN_MANAGER"] is None:
        state["_TOKEN_MANAGER"] = TokenManager()
    return state["_TOKEN_MANAGER"]


def initialize_tokens(*, force_reload: bool = False) -> TokenManager:
    """初始化应用上下文并产出令牌快照。

    参数:
    - force_reload: 是否强制重载配置库。

    返回:
    - TokenManager: 已加载的令牌管理器。
    """
    initialize_app_context(force_reload=force_reload)
    return get_token_manager(reset=True).load()
