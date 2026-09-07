"""配置校验模块。

职责:
- 提供语言包配置的校验函数。
- 保留通用校验辅助工具。

说明:
- 窗口设置与主题颜色的校验已迁移至 ``token_models`` 中的 pydantic 模型，
  本模块仅保留语言包校验及共用辅助。
"""

from typing import NoReturn

from AppCore.SYS.module.attrdict import AttrDict


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


def _as_dict(data: object) -> object:
    """将 AttrDict 兼容转换为标准字典。

    参数:
    - data: 可能为 AttrDict 或 dict 的对象。

    返回:
    - object: 转换后的 dict 或原对象。
    """
    if isinstance(data, AttrDict):
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


def validate_language_data(language_data: object, language_name: str = "unknown") -> None:
    """校验语言包配置数据。

    参数:
    - language_data: 语言对象，支持 dict 或 AttrDict。
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
