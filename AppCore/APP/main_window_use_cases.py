"""模块说明。"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class ButtonDecision:
    """按钮决策结果对象。

    职责:
    - 表达按钮处理后的分发类型与附加载荷。

    属性:
    - kind: 决策类型，如 ``page_route``、``action``、``plugin_command``。
    - payload: 决策载荷，具体结构由 ``kind`` 决定。
    """

    kind: str
    payload: object | None = None


class MainWindowButtonUseCase:
    """主窗口按钮决策用例。

    职责:
    - 统一按钮事件的业务判定逻辑。
    - 根据按钮与路由信息返回标准化决策结果。
    """

    ACTION_MAP: ClassVar[dict[str, str]] = {
        "btn_info": "btn_info",
        "btn_more": "btn_more",
        "btn_close_left_column": "btn_more",
        "btn_top_settings": "btn_top_settings",
        "btn_language": "btn_language",
        "btn_themes": "btn_themes",
    }

    @staticmethod
    def should_reset_left_tab(btn_name: str) -> bool:
        """判断是否需要重置左侧标签激活状态。

        参数:
        - btn_name: 当前点击按钮的对象名。

        返回:
        - bool: ``True`` 表示需要重置，``False`` 表示保持当前状态。
        """
        return btn_name != "btn_settings"

    @classmethod
    def decide(cls, btn_name: str, route: tuple[str, str] | None) -> ButtonDecision:
        """根据按钮与路由信息生成统一决策。

        参数:
        - cls: 类对象。
        - btn_name: 当前点击按钮的对象名。
        - route: 页面路由信息，格式为 ``(page_name, title)``，无路由时为 ``None``。

        返回:
        - ButtonDecision: 包含决策类型与载荷的不可变对象。
        """
        if route is not None:
            return ButtonDecision(kind="page_route", payload=route)

        action_name = cls.ACTION_MAP.get(btn_name)
        if action_name is not None:
            return ButtonDecision(kind="action", payload=action_name)

        return ButtonDecision(kind="plugin_command", payload=btn_name)
