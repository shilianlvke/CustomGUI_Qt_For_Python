import threading
from dataclasses import dataclass

# FIX-07: 调色板写入使用模块级可重入锁：主题切换时 update() 整体生效；
# 读侧（自绘组件在 paintEvent 中直接读属性）不加锁，避免影响高频绘制。
_PALETTE_LOCK = threading.RLock()


@dataclass
class ColorHandler:
    # 默认暗色系（Fluent 中性色阶）
    custom_dark_one: str = "#1c1c1c"
    custom_dark_two: str = "#202020"
    custom_dark_three: str = "#242424"
    custom_dark_four: str = "#2d2d2d"

    # 背景色
    custom_bg_one: str = "#202020"
    custom_bg_two: str = "#2b2b2b"
    custom_bg_three: str = "#323232"
    custom_bg_active_one: str = "#6ccb5f"
    custom_bg_active_two: str = "#fce100"
    custom_bg_active_three: str = "#ff99a4"

    # 图标颜色
    custom_icon_color: str = "#c5c5c5"
    custom_icon_hover: str = "#ffffff"
    custom_icon_pressed: str = "#4cc2ff"
    custom_icon_active: str = "#ffffff"

    # 上下文颜色
    custom_context_color: str = "#4cc2ff"
    custom_context_hover: str = "#6fd0ff"
    custom_context_pressed: str = "#3aa7e0"

    # 文本颜色
    custom_text_title: str = "#ffffff"
    custom_text_foreground: str = "#cfcfcf"
    custom_text_description: str = "#919191"
    custom_text_active: str = "#ffffff"

    # 基础颜色
    custom_white: str = "#ffffff"
    custom_pink: str = "#ff99a4"
    custom_green: str = "#6ccb5f"
    custom_red: str = "#ff99a4"
    custom_yellow: str = "#fce100"
    custom_transparent: str = "transparent"

    def update(self, new_colors: dict) -> None:
        # 注册颜色，允许用自定义颜色
        # FIX-07: 逐字段 setattr 期间持锁，避免并发主题切换读到半更新调色板。
        with _PALETTE_LOCK:
            for key, value in new_colors.items():
                setattr(self, key, value)


ColorPalette = ColorHandler()
__all__ = ["ColorHandler", "ColorPalette"]
