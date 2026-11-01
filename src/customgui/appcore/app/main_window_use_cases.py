from dataclasses import dataclass


@dataclass(frozen=True)
class ButtonDecision:
    kind: str
    payload: object | None = None


class MainWindowButtonUseCase:
    ACTION_MAP = {
        "btn_info": "btn_info",
        "btn_more": "btn_more",
        "btn_close_left_column": "btn_more",
        "btn_top_settings": "btn_top_settings",
        "btn_language": "btn_language",
        "btn_themes": "btn_themes",
    }

    @staticmethod
    def should_reset_left_tab(btn_name: str) -> bool:
        return btn_name != "btn_settings"

    @classmethod
    def decide(cls, btn_name: str, route: tuple[str, str] | None) -> ButtonDecision:
        if route is not None:
            return ButtonDecision(kind="page_route", payload=route)

        action_name = cls.ACTION_MAP.get(btn_name)
        if action_name is not None:
            return ButtonDecision(kind="action", payload=action_name)

        return ButtonDecision(kind="plugin_command", payload=btn_name)
