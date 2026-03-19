from dataclasses import dataclass, fields

from easydict import EasyDict

from .color_module import ColorHandler


@dataclass(frozen=True)
class SizeRangeSchema:
	minimum: int
	maximum: int


@dataclass(frozen=True)
class WindowSettingsSchema:
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


def _as_dict(data):
	if isinstance(data, EasyDict):
		return dict(data)
	return data


def _ensure_keys(data, required_keys, label):
	missing = [key for key in required_keys if key not in data]
	if missing:
		raise ValueError(f"{label} 缺少关键字段: {', '.join(missing)}")


def _validate_size_range(raw_value, field_name):
	raw_value = _as_dict(raw_value)
	if not isinstance(raw_value, dict):
		raise ValueError(f"{field_name} 必须是包含 minimum/maximum 的字典")
	_ensure_keys(raw_value, ["minimum", "maximum"], field_name)

	minimum = raw_value["minimum"]
	maximum = raw_value["maximum"]
	if not isinstance(minimum, int) or not isinstance(maximum, int):
		raise ValueError(f"{field_name}.minimum/maximum 必须为整数")
	if minimum < 0 or maximum < 0:
		raise ValueError(f"{field_name}.minimum/maximum 不能为负数")
	if minimum > maximum:
		raise ValueError(f"{field_name}.minimum 不能大于 maximum")

	return SizeRangeSchema(minimum=minimum, maximum=maximum)


def _validate_size_list(raw_value, field_name):
	if not isinstance(raw_value, list) or len(raw_value) != 2:
		raise ValueError(f"{field_name} 必须是长度为 2 的数组")
	if not all(isinstance(v, int) for v in raw_value):
		raise ValueError(f"{field_name} 必须仅包含整数")
	if raw_value[0] <= 0 or raw_value[1] <= 0:
		raise ValueError(f"{field_name} 宽高必须大于 0")


def validate_settings_data(settings_data):
	settings = _as_dict(settings_data)
	if not isinstance(settings, dict):
		raise ValueError("AppSettings 必须为字典结构")

	required = [item.name for item in fields(WindowSettingsSchema)]
	_ensure_keys(settings, required, "AppSettings")

	_validate_size_list(settings["startup_size"], "startup_size")
	_validate_size_list(settings["minimum_size"], "minimum_size")
	if settings["startup_size"][0] < settings["minimum_size"][0] or settings["startup_size"][1] < settings["minimum_size"][1]:
		raise ValueError("startup_size 不能小于 minimum_size")

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
			raise ValueError(f"{key} 必须是非负整数")

	bool_fields = ["custom_title_bar", "hide_grips", "window_shadow"]
	for key in bool_fields:
		if not isinstance(settings[key], bool):
			raise ValueError(f"{key} 必须是布尔值")

	if not isinstance(settings["family"], str) or not settings["family"].strip():
		raise ValueError("family 必须是非空字符串")


def validate_theme_data(theme_data, theme_name="unknown"):
	theme = _as_dict(theme_data)
	if not isinstance(theme, dict):
		raise ValueError(f"主题 {theme_name} 必须是字典结构")

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
			raise ValueError(f"主题 {theme_name} 字段 {key} 必须是非空字符串")


def validate_language_data(language_data, language_name="unknown"):
	language = _as_dict(language_data)
	if not isinstance(language, dict):
		raise ValueError(f"语言 {language_name} 必须是字典结构")

	_ensure_keys(language, ["custom_ui", "PAGE", "UI"], f"语言 {language_name}")

	custom_ui = _as_dict(language["custom_ui"])
	if not isinstance(custom_ui, dict):
		raise ValueError(f"语言 {language_name}.custom_ui 必须是字典")
	_ensure_keys(
		custom_ui,
		["sys_name", "sys_version", "sys_copyright", "sys_github"],
		f"语言 {language_name}.custom_ui",
	)

	page = _as_dict(language["PAGE"])
	if not isinstance(page, dict):
		raise ValueError(f"语言 {language_name}.PAGE 必须是字典")
	_ensure_keys(page, ["widget_show"], f"语言 {language_name}.PAGE")

	ui = _as_dict(language["UI"])
	if not isinstance(ui, dict):
		raise ValueError(f"语言 {language_name}.UI 必须是字典")
	_ensure_keys(ui, ["ui_Settings", "ui_Show", "ui_Hide"], f"语言 {language_name}.UI")
