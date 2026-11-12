import threading
from dataclasses import dataclass

# FIX-07: 调色板写入使用模块级可重入锁：主题切换时 update() 整体生效；
# 读侧（自绘组件在 paintEvent 中直接读属性）不加锁，避免影响高频绘制。
_PALETTE_LOCK = threading.RLock()


@dataclass
class ColorHandler:
    """全局调色板（默认值与 ``themes/default.yaml`` 的 Grove 主题一致）。

    七档中性色按**表面阶梯**编号，深浅主题共用同一套语义：

    ====================== =========================================
    ``custom_dark_one``    侧栏（下沉层，最深）
    ``custom_bg_one``      画布（窗口主背景）
    ``custom_dark_two``    面板（标题栏 / 抽屉 / 区域卡片基底）
    ``custom_dark_three``  卡片（内容层）
    ``custom_dark_four``   抬升层（中性按钮、下拉框、选中块）
    ``custom_bg_two``      交互悬停
    ``custom_bg_three``    交互按下
    ====================== =========================================
    """

    # 表面阶梯
    custom_dark_one: str = "#0d1113"
    custom_dark_two: str = "#171c1f"
    custom_dark_three: str = "#1c2225"
    custom_dark_four: str = "#242b2e"

    # 画布与交互层
    custom_bg_one: str = "#121619"
    custom_bg_two: str = "#2a3236"
    custom_bg_three: str = "#333c41"
    custom_bg_active_one: str = "#6fd08c"
    custom_bg_active_two: str = "#f2c65a"
    custom_bg_active_three: str = "#ff8f87"

    # 图标颜色
    custom_icon_color: str = "#9caaa0"
    custom_icon_hover: str = "#ffffff"
    custom_icon_pressed: str = "#a3e57f"
    custom_icon_active: str = "#ffffff"

    # 强调色（品牌果绿）
    custom_context_color: str = "#a3e57f"
    custom_context_hover: str = "#b7ee99"
    custom_context_pressed: str = "#8ad165"

    # 文本颜色
    custom_text_title: str = "#f4f7f3"
    custom_text_foreground: str = "#dfe6df"
    custom_text_description: str = "#98a59b"
    custom_text_active: str = "#ffffff"

    # 基础颜色
    custom_white: str = "#ffffff"
    custom_black: str = "#000000"
    custom_pink: str = "#f0a8c0"
    custom_green: str = "#6fd08c"
    custom_red: str = "#ff8f87"
    custom_yellow: str = "#f2c65a"
    # 语义色补充：信息 / 帮助各自有独立色相，避免与品牌强调色撞车
    custom_info: str = "#7cc7ff"
    custom_help: str = "#c9a7ff"
    custom_transparent: str = "transparent"

    def update(self, new_colors: dict) -> None:
        # 注册颜色，允许用自定义颜色
        # FIX-07: 逐字段 setattr 期间持锁，避免并发主题切换读到半更新调色板。
        with _PALETTE_LOCK:
            for key, value in new_colors.items():
                setattr(self, key, value)


ColorPalette = ColorHandler()

#: 颜色选择器的预设色板（组件只引用，不在组件内定义颜色）
COLOR_SWATCHES: tuple[str, ...] = (
    "#ef4444",
    "#f97316",
    "#f59e0b",
    "#eab308",
    "#84cc16",
    "#22c55e",
    "#10b981",
    "#14b8a6",
    "#06b6d4",
    "#0ea5e9",
    "#3b82f6",
    "#6366f1",
    "#8b5cf6",
    "#a855f7",
    "#d946ef",
    "#ec4899",
    "#f43f5e",
    "#64748b",
    "#0f172a",
    "#ffffff",
    "#f1f5f9",
    "#94a3b8",
    "#475569",
    "#000000",
)

__all__ = ["COLOR_SWATCHES", "ColorHandler", "ColorPalette"]
