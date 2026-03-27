"""模块说明。"""

from dataclasses import dataclass, fields
from typing import NoReturn

from easydict import EasyDict

from .color_module import ColorHandler

SIZE_PAIR_LEN = 2


class SettingsValidationError(ValueError):
    """配置校验值错误。"""


class SettingsTypeError(TypeError):
    """配置校验类型错误。"""


def _raise_validation_error(message: str) -> NoReturn:
    """抛出配置值校验异常。"""
    raise SettingsValidationError(message)


def _raise_type_error(message: str) -> NoReturn:
    """抛出配置类型校验异常。"""
    raise SettingsTypeError(message)


@dataclass(frozen=True)
class SizeRangeSchema:
    """最小/最大区间结构。"""

    minimum: int
    maximum: int


@dataclass(frozen=True)
class WindowSettingsSchema:
    """窗口设置字段结构定义。"""

    startup_size: list
    minimum_size: list
    icon_size: int
    custom_title_bar: bool
    hide_grips: bool
    window_margin: int
    window_space: int
    window_border_size: int
    window_border_radius: int
    window_shadow: bool
    lef_menu_size: SizeRangeSchema
    left_menu_content_margins: int
    left_column_size: SizeRangeSchema
    right_column_size: SizeRangeSchema
    custom_padding: int
    custom_border: int
    tooltip_border_radius: int
    tooltip_font: int
    time_animation: int
    family: str
    title_size: int
    subtitle_size: int
    text_size: int


def _as_dict(data: object) -> object:
    """将 EasyDict 兼容转换为标准字典。

    参数:
    - data: 可能为 EasyDict 或 dict 的对象。

    返回:
    - object: 转换后的 dict 或原对象。
    """
    if isinstance(data, EasyDict):
        return dict(data)
    return data


def _ensure_keys(data: dict[str, object], required_keys: list[str], label: str) -> None:
    """校验字典必须包含给定键集合。

    参数:
    - data: 待校验字典。
    - required_keys: 必填键列表。
    - label: 错误提示标签。

    返回:
    - None
    """
    missing = [key for key in required_keys if key not in data]
    if missing:
        _raise_validation_error(f"{label} 缺少关键字段: {', '.join(missing)}")


def _validate_size_range(raw_value: object, field_name: str) -> SizeRangeSchema:
    """校验区间字段并返回标准结构。

    参数:
    - raw_value: 待校验区间对象。
    - field_name: 字段名，用于错误信息。

    返回:
    - SizeRangeSchema: 校验通过后的区间对象。
    """
    raw_value = _as_dict(raw_value)
    if not isinstance(raw_value, dict):
        _raise_type_error(f"{field_name} 必须是包含 minimum/maximum 的字典")
    _ensure_keys(raw_value, ["minimum", "maximum"], field_name)

    minimum = raw_value["minimum"]
    maximum = raw_value["maximum"]
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        _raise_type_error(f"{field_name}.minimum/maximum 必须为整数")
    if minimum < 0 or maximum < 0:
        _raise_validation_error(f"{field_name}.minimum/maximum 不能为负数")
    if minimum > maximum:
        _raise_validation_error(f"{field_name}.minimum 不能大于 maximum")

    return SizeRangeSchema(minimum=minimum, maximum=maximum)


def _validate_size_list(raw_value: object, field_name: str) -> None:
    """校验尺寸数组字段。

    参数:
    - raw_value: 待校验值，应为长度为 2 的整数数组。
    - field_name: 字段名，用于错误信息。

    返回:
    - None
    """
    if not isinstance(raw_value, list) or len(raw_value) != SIZE_PAIR_LEN:
        _raise_type_error(f"{field_name} 必须是长度为 {SIZE_PAIR_LEN} 的数组")
    if not all(isinstance(v, int) for v in raw_value):
        _raise_type_error(f"{field_name} 必须仅包含整数")
    if raw_value[0] <= 0 or raw_value[1] <= 0:
        _raise_validation_error(f"{field_name} 宽高必须大于 0")


def validate_settings_data(settings_data: object) -> None:
    """校验应用窗口设置数据。

    参数:
    - settings_data: 配置对象，支持 dict 或 EasyDict。

    返回:
    - None
    """
    settings = _as_dict(settings_data)
    if not isinstance(settings, dict):
        _raise_type_error("AppSettings 必须为字典结构")

    required = [item.name for item in fields(WindowSettingsSchema)]
    _ensure_keys(settings, required, "AppSettings")

    _validate_size_list(settings["startup_size"], "startup_size")
    _validate_size_list(settings["minimum_size"], "minimum_size")
    if (
        settings["startup_size"][0] < settings["minimum_size"][0]
        or settings["startup_size"][1] < settings["minimum_size"][1]
    ):
        _raise_validation_error("startup_size 不能小于 minimum_size")

    _validate_size_range(settings["lef_menu_size"], "lef_menu_size")
    _validate_size_range(settings["left_column_size"], "left_column_size")
    _validate_size_range(settings["right_column_size"], "right_column_size")

    int_fields = [
        "icon_size",
        "window_margin",
        "window_space",
        "window_border_size",
        "window_border_radius",
        "left_menu_content_margins",
        "custom_padding",
        "custom_border",
        "tooltip_border_radius",
        "tooltip_font",
        "time_animation",
        "title_size",
        "subtitle_size",
        "text_size",
    ]
    for key in int_fields:
        value = settings[key]
        if not isinstance(value, int) or value < 0:
            _raise_type_error(f"{key} 必须是非负整数")

    bool_fields = ["custom_title_bar", "hide_grips", "window_shadow"]
    for key in bool_fields:
        if not isinstance(settings[key], bool):
            _raise_type_error(f"{key} 必须是布尔值")

    if not isinstance(settings["family"], str) or not settings["family"].strip():
        _raise_type_error("family 必须是非空字符串")


def validate_theme_data(theme_data: object, theme_name: str = "unknown") -> None:
    """校验主题颜色配置数据。

    参数:
    - theme_data: 主题对象，支持 dict 或 EasyDict。
    - theme_name: 主题名称，用于错误信息。

    返回:
    - None
    """
    theme = _as_dict(theme_data)
    if not isinstance(theme, dict):
        _raise_type_error(f"主题 {theme_name} 必须是字典结构")

    optional_keys = {
        "custom_bg_active_one",
        "custom_bg_active_two",
        "custom_bg_active_three",
        "custom_transparent",
    }
    required = [item.name for item in fields(ColorHandler) if item.name not in optional_keys]
    _ensure_keys(theme, required, f"主题 {theme_name}")

    for key, value in theme.items():
        if not isinstance(value, str) or not value.strip():
            _raise_type_error(f"主题 {theme_name} 字段 {key} 必须是非空字符串")


def validate_language_data(language_data: object, language_name: str = "unknown") -> None:
    """校验语言包配置数据。

    参数:
    - language_data: 语言对象，支持 dict 或 EasyDict。
    - language_name: 语言名称，用于错误信息。

    返回:
    - None
    """
    language = _as_dict(language_data)
    if not isinstance(language, dict):
        _raise_type_error(f"语言 {language_name} 必须是字典结构")

    _ensure_keys(language, ["custom_ui", "PAGE", "UI"], f"语言 {language_name}")

    custom_ui = _as_dict(language["custom_ui"])
    if not isinstance(custom_ui, dict):
        _raise_type_error(f"语言 {language_name}.custom_ui 必须是字典")
    _ensure_keys(
        custom_ui,
        ["sys_name", "sys_version", "sys_copyright", "sys_github"],
        f"语言 {language_name}.custom_ui",
    )

    page = _as_dict(language["PAGE"])
    if not isinstance(page, dict):
        _raise_type_error(f"语言 {language_name}.PAGE 必须是字典")
    _ensure_keys(page, ["widget_show"], f"语言 {language_name}.PAGE")

    ui = _as_dict(language["UI"])
    if not isinstance(ui, dict):
        _raise_type_error(f"语言 {language_name}.UI 必须是字典")
    _ensure_keys(ui, ["ui_Settings", "ui_Show", "ui_Hide"], f"语言 {language_name}.UI")
