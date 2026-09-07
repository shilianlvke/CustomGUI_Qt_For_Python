"""pydantic 配置模型。

职责:
- 以声明式模型承载窗口设置与主题颜色的 schema。
- 替代手写校验函数，提供强类型、冻结快照与清晰的错误信息。

设计说明:
- 所有模型使用 ``frozen=True``，实例不可变，适合作为运行时快照。
- ``extra="ignore"`` 允许合并后的配置携带额外字段（如 config/console 中的
  ``language``、``logger_level``），仅校验本模型关心的字段。
- 字符串字段统一 ``str_strip_whitespace`` 并 ``str_min_length=1``，
  与旧手写校验的「非空字符串」语义对齐。
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["SizeRange", "ThemeColors", "WindowSettings"]


class SizeRange(BaseModel):
    """最小/最大区间结构。"""

    model_config = ConfigDict(frozen=True)

    minimum: int = Field(ge=0)
    maximum: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> "SizeRange":
        """校验 minimum 不大于 maximum。"""
        if self.minimum > self.maximum:
            raise ValueError("minimum 不能大于 maximum")
        return self


class WindowSettings(BaseModel):
    """窗口与应用设置模型。"""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        str_strip_whitespace=True,
        str_min_length=1,
    )

    startup_size: tuple[int, int]
    minimum_size: tuple[int, int]
    icon_size: int = Field(ge=0)
    custom_title_bar: bool
    hide_grips: bool
    window_margin: int = Field(ge=0)
    window_space: int = Field(ge=0)
    window_border_size: int = Field(ge=0)
    window_border_radius: int = Field(ge=0)
    window_shadow: bool
    lef_menu_size: SizeRange
    left_menu_content_margins: int = Field(ge=0)
    left_column_size: SizeRange
    right_column_size: SizeRange
    custom_padding: int = Field(ge=0)
    custom_border: int = Field(ge=0)
    tooltip_border_radius: int = Field(ge=0)
    tooltip_font: int = Field(ge=0)
    time_animation: int = Field(ge=0)
    family: str
    title_size: int = Field(ge=0)
    subtitle_size: int = Field(ge=0)
    text_size: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_startup_ge_minimum(self) -> "WindowSettings":
        """校验初始尺寸不小于最小尺寸。"""
        if self.startup_size[0] < self.minimum_size[0] or self.startup_size[1] < self.minimum_size[1]:
            raise ValueError("startup_size 不能小于 minimum_size")
        return self


class ThemeColors(BaseModel):
    """主题颜色模型。"""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        str_strip_whitespace=True,
        str_min_length=1,
    )

    # 暗色层级
    custom_dark_one: str
    custom_dark_two: str
    custom_dark_three: str
    custom_dark_four: str

    # 背景色
    custom_bg_one: str
    custom_bg_two: str
    custom_bg_three: str

    # 图标颜色
    custom_icon_color: str
    custom_icon_hover: str
    custom_icon_pressed: str
    custom_icon_active: str

    # 上下文颜色
    custom_context_color: str
    custom_context_hover: str
    custom_context_pressed: str

    # 文本颜色
    custom_text_title: str
    custom_text_foreground: str
    custom_text_description: str
    custom_text_active: str

    # 基础颜色
    custom_white: str
    custom_pink: str
    custom_green: str
    custom_red: str
    custom_yellow: str

    # 可选颜色（主题文件可省略，使用默认值）
    custom_bg_active_one: str = "#57965c"
    custom_bg_active_two: str = "#ffcf49"
    custom_bg_active_three: str = "#c94f4f"
    custom_transparent: str = "transparent"
