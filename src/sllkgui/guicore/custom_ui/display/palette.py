"""状态原子件的主题色（与基座调色板对齐，切换主题实时生效）。"""

from __future__ import annotations

from PySide6.QtGui import QColor

from sllkgui.appcore import ColorPalette


def is_dark_theme() -> bool:
    """按内容区背景亮度判断主题深浅（四套主题通用）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def tokens() -> dict[str, str]:
    """Tag / Chip / Avatar / Skeleton / Divider 共用的中性色阶。"""
    if is_dark_theme():
        return {
            "surface": ColorPalette.custom_dark_four,
            "surface_strong": ColorPalette.custom_bg_two,
            "skeleton": ColorPalette.custom_dark_four,
            "border": ColorPalette.custom_dark_four,
            "text": ColorPalette.custom_text_title,
            "muted": ColorPalette.custom_text_description,
            "accent": ColorPalette.custom_context_color,
        }
    return {
        # 浅色主题也走调色板：bright / eye 各自的中性色阶不同，若继续写死灰度，
        # 护眼主题里的 Tag/Chip/上传区会混入一块与主题无关的灰色。
        "surface": ColorPalette.custom_dark_two,
        "surface_strong": ColorPalette.custom_bg_three,
        "skeleton": ColorPalette.custom_dark_four,
        "border": ColorPalette.custom_dark_four,
        "text": ColorPalette.custom_text_title,
        "muted": ColorPalette.custom_text_description,
        "accent": ColorPalette.custom_context_color,
    }


def content_surface_color() -> QColor:
    """卡片内小表面（Chip、媒体占位、文件行等）的玻璃填充色。

    这些小表面叠在卡片玻璃之上，若继续用不透明的 ``tokens()["surface"]``，
    会在半透明卡片里留下补丁。这里与 ``CTimeline`` / 上传拖放区使用同一套
    ``glass_surface`` 写法：亚克力开启时按 ``glass.card`` 降低不透明度并保留
    0.10 下限，关闭时回落为原始实色。
    """
    # 延迟导入：acrylic 依赖 appcore 配置，palette 被大量组件在导入期引用，
    # 模块级互相导入容易形成初始化顺序问题。
    from sllkgui.appcore import AppSettings

    from ...acrylic import glass_surface

    return glass_surface(tokens()["surface"], AppSettings.glass.card, minimum=0.10)


__all__ = ["content_surface_color", "is_dark_theme", "tokens"]
