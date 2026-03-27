"""模块说明。"""

from dataclasses import dataclass


@dataclass
class ColorHandler:
    """颜色配置容器。

    职责:
    - 持有主题相关颜色字段。
    - 提供运行时批量更新颜色值的能力。
    """

    # 默认暗色系
    custom_dark_one: str = "#1b1e23"
    custom_dark_two: str = "#1e2229"
    custom_dark_three: str = "#21252d"
    custom_dark_four: str = "#272c36"

    # 背景色
    custom_bg_one: str = "#2c313c"
    custom_bg_two: str = "#343b48"
    custom_bg_three: str = "#3c4454"
    custom_bg_active_one: str = "#57965c"
    custom_bg_active_two: str = "#ffcf49"
    custom_bg_active_three: str = "#c94f4f"

    # 图标颜色
    custom_icon_color: str = "#c3ccdf"
    custom_icon_hover: str = "#dce1ec"
    custom_icon_pressed: str = "#6c99f4"
    custom_icon_active: str = "#f5f6f9"

    # 上下文颜色
    custom_context_color: str = "#568af2"
    custom_context_hover: str = "#6c99f4"
    custom_context_pressed: str = "#3f6fd1"

    # 文本颜色
    custom_text_title: str = "#dce1ec"
    custom_text_foreground: str = "#8a95aa"
    custom_text_description: str = "#4f5b6e"
    custom_text_active: str = "#dce1ec"

    # 基础颜色
    custom_white: str = "#f5f6f9"
    custom_pink: str = "#ff007f"
    custom_green: str = "#57965c"
    custom_red: str = "#c94f4f"
    custom_yellow: str = "#ffcf49"
    custom_transparent: str = "transparent"

    def update(self, new_colors: dict) -> None:
        """批量更新颜色字段。

        参数:
        - new_colors: 颜色键值映射，键为字段名，值为颜色字符串。

        返回:
        - None
        """
        # 注册颜色，允许用自定义颜色
        for key, value in new_colors.items():
            setattr(self, key, value)


ColorPalette = ColorHandler()
__all__ = ["ColorHandler", "ColorPalette"]
