"""配置系统重构后的新框架测试：Attrs、类型化模型、注册表、YamlHandler。"""

import pytest

from AppCore import (
    AppLanguages,
    AppSettings,
    AppThemes,
    Attrs,
    YamlHandler,
    get_app_context,
    initialize_app_context,
)
from AppCore.SYS.config.mapping import deep_merge, to_attrs, to_dict
from AppCore.SYS.config.registry import ConfigFile, ConfigRegistry
from AppCore.SYS.config.schema import (
    AppSettingsModel,
    SizeRange,
    from_mapping,
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)
from AppCore.SYS.config.yaml_io import dump_yaml_file, load_yaml_file
from AppCore.SYS.module.error_module import DomainErrorBoundary, IOErrorBoundary


# ---------------------------------------------------------------------------
# Attrs（属性访问映射）
# ---------------------------------------------------------------------------


def test_attrs_attribute_and_item_access():
    data = to_attrs({"window": {"width": 960}, "title": "demo"})

    assert data.window.width == 960
    assert data["window"]["width"] == 960
    assert data.title == "demo"


def test_attrs_missing_key_raises_attribute_error_for_getattr_default():
    data = Attrs(a=1)

    with pytest.raises(AttributeError):
        _ = data.missing
    assert getattr(data, "missing", "fallback") == "fallback"


def test_attrs_get_path_and_merge():
    data = to_attrs({"database": {"host": "localhost"}})

    assert data.get_path("database.host") == "localhost"
    assert data.get_path("database.port", 3306) == 3306

    data.merge({"database": {"port": 3306}, "extra": {"nested": 1}})
    assert data.database.port == 3306
    assert data.extra.nested == 1


def test_deep_merge_recurses_dicts_and_replaces_lists():
    target = {"a": {"x": 1, "keep": True}, "items": [1, 2]}
    deep_merge(target, {"a": {"y": 2}, "items": [3]})

    assert target["a"]["x"] == 1
    assert target["a"]["y"] == 2
    assert target["items"] == [3]


def test_to_dict_roundtrip():
    original = {"a": {"b": [1, {"c": 2}]}}
    assert to_dict(to_attrs(original)) == original


# ---------------------------------------------------------------------------
# 类型化模型与通用强制转换引擎
# ---------------------------------------------------------------------------


def test_size_range_coercion_from_mapping():
    model = from_mapping(SizeRange, {"minimum": 0, "maximum": 240}, label="SizeRange")

    assert model.minimum == 0
    assert model.maximum == 240


def test_size_range_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="minimum 不能大于 maximum"):
        from_mapping(SizeRange, {"minimum": 5, "maximum": 1}, label="SizeRange")


def test_app_settings_model_coerces_full_payload():
    payload = {
        "startup_size": [960, 540],
        "minimum_size": [960, 540],
        "icon_size": 32,
        "custom_title_bar": True,
        "hide_grips": True,
        "window_margin": 2,
        "window_space": 2,
        "window_border_size": 2,
        "window_border_radius": 10,
        "window_shadow": True,
        "lef_menu_size": {"minimum": 50, "maximum": 200},
        "left_menu_content_margins": 2,
        "left_column_size": {"minimum": 0, "maximum": 240},
        "right_column_size": {"minimum": 0, "maximum": 240},
        "right_menu_content_margins": 3,
        "right_title_bar_height": 40,
        "right_content_space": 6,
        "right_credits_height": 40,
        "custom_padding": 10,
        "custom_border": 3,
        "tooltip_border_radius": 17,
        "tooltip_font": 300,
        "time_animation": 500,
        "family": "微软雅黑",
        "title_size": 18,
        "subtitle_size": 15,
        "text_size": 12,
        "language": "zh_cn",
        "theme_name": "default",
        "logo": "icon",
        "logo_home": "mihoutao",
        "logo_title": "mihoutao",
        "logo_loading": "zig",
        "display": ["banner"],
        "logger_level": "DEBUG",
        "logger_color": True,
    }

    model = validate_settings_data(payload)

    assert isinstance(model, AppSettingsModel)
    assert model.startup_size == (960, 540)
    assert model.lef_menu_size.minimum == 50
    assert model.theme_name == "default"


def test_app_settings_model_rejects_missing_field():
    payload = {"startup_size": [960, 540]}
    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_settings_data(payload)


def test_app_settings_model_rejects_wrong_types():
    payload = {
        "startup_size": "large",  # 错误类型
        "minimum_size": [960, 540],
        "icon_size": 32,
        "custom_title_bar": True,
        "hide_grips": True,
        "window_margin": 2,
        "window_space": 2,
        "window_border_size": 2,
        "window_border_radius": 10,
        "window_shadow": True,
        "lef_menu_size": {"minimum": 50, "maximum": 200},
        "left_menu_content_margins": 2,
        "left_column_size": {"minimum": 0, "maximum": 240},
        "right_column_size": {"minimum": 0, "maximum": 240},
        "right_menu_content_margins": 3,
        "right_title_bar_height": 40,
        "right_content_space": 6,
        "right_credits_height": 40,
        "custom_padding": 10,
        "custom_border": 3,
        "tooltip_border_radius": 17,
        "tooltip_font": 300,
        "time_animation": 500,
        "family": "微软雅黑",
        "title_size": 18,
        "subtitle_size": 15,
        "text_size": 12,
        "language": "zh_cn",
        "theme_name": "default",
        "logo": "icon",
        "logo_home": "mihoutao",
        "logo_title": "mihoutao",
        "logo_loading": "zig",
        "display": ["banner"],
        "logger_level": "DEBUG",
        "logger_color": True,
    }
    with pytest.raises(ValueError, match="startup_size"):
        validate_settings_data(payload)


def test_app_settings_model_rejects_startup_smaller_than_minimum():
    payload = {
        "startup_size": [100, 100],
        "minimum_size": [960, 540],
        "icon_size": 32,
        "custom_title_bar": True,
        "hide_grips": True,
        "window_margin": 2,
        "window_space": 2,
        "window_border_size": 2,
        "window_border_radius": 10,
        "window_shadow": True,
        "lef_menu_size": {"minimum": 50, "maximum": 200},
        "left_menu_content_margins": 2,
        "left_column_size": {"minimum": 0, "maximum": 240},
        "right_column_size": {"minimum": 0, "maximum": 240},
        "right_menu_content_margins": 3,
        "right_title_bar_height": 40,
        "right_content_space": 6,
        "right_credits_height": 40,
        "custom_padding": 10,
        "custom_border": 3,
        "tooltip_border_radius": 17,
        "tooltip_font": 300,
        "time_animation": 500,
        "family": "微软雅黑",
        "title_size": 18,
        "subtitle_size": 15,
        "text_size": 12,
        "language": "zh_cn",
        "theme_name": "default",
        "logo": "icon",
        "logo_home": "mihoutao",
        "logo_title": "mihoutao",
        "logo_loading": "zig",
        "display": ["banner"],
        "logger_level": "DEBUG",
        "logger_color": True,
    }
    with pytest.raises(ValueError, match="startup_size 不能小于 minimum_size"):
        validate_settings_data(payload)


def test_theme_model_optional_fields_default_to_none():
    payload = {
        "custom_dark_one": "#000001",
        "custom_dark_two": "#000002",
        "custom_dark_three": "#000003",
        "custom_dark_four": "#000004",
        "custom_bg_one": "#000005",
        "custom_bg_two": "#000006",
        "custom_bg_three": "#000007",
        "custom_icon_color": "#000008",
        "custom_icon_hover": "#000009",
        "custom_icon_pressed": "#00000a",
        "custom_icon_active": "#00000b",
        "custom_context_color": "#00000c",
        "custom_context_hover": "#00000d",
        "custom_context_pressed": "#00000e",
        "custom_text_title": "#00000f",
        "custom_text_foreground": "#000010",
        "custom_text_description": "#000011",
        "custom_text_active": "#000012",
        "custom_white": "#000013",
        "custom_pink": "#000014",
        "custom_green": "#000015",
        "custom_red": "#000016",
        "custom_yellow": "#000017",
    }

    model = validate_theme_data(payload, "plain")

    assert model.custom_bg_active_one is None
    assert model.custom_transparent is None


def test_theme_validation_rejects_empty_value():
    payload = {"custom_dark_one": ""}
    with pytest.raises(ValueError, match="必须是非空字符串"):
        validate_theme_data(payload, "broken")


def test_language_validation_requires_group_keys():
    with pytest.raises(ValueError, match="缺少关键字段"):
        validate_language_data({"custom_ui": {}, "PAGE": {}, "UI": {}}, "broken")


# ---------------------------------------------------------------------------
# 注册表与全局上下文（真实资源文件）
# ---------------------------------------------------------------------------


def test_app_settings_view_exposes_typed_fields():
    initialize_app_context(force_reload=True)

    assert AppSettings.family == "微软雅黑"
    assert AppSettings.startup_size == (960, 540)
    assert AppSettings.lef_menu_size.minimum == 50
    assert AppSettings.left_column_size.maximum == 240
    assert AppSettings.logo == "icon"
    assert isinstance(AppSettings.display, list)


def test_context_groups_load_real_resources():
    ctx = get_app_context(force_reload=True)

    assert {"default", "bright", "dracula", "eye"} <= set(ctx.themes.keys())
    assert {"zh_cn", "en_us"} <= set(ctx.languages.keys())
    assert ctx.others  # DevelopInfo / DevelopLog 等

    assert AppSettings.theme_name in AppThemes
    assert AppSettings.language in AppLanguages

    theme_data = AppThemes[AppSettings.theme_name].data
    assert theme_data.custom_bg_one.startswith("#")

    lang_data = AppLanguages[AppSettings.language].data
    assert lang_data.custom_ui.sys_name


def test_context_is_cwd_independent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ctx = get_app_context(force_reload=True)

    assert ctx.settings.family == "微软雅黑"
    assert AppSettings.logo_home == "mihoutao"


def _valid_theme_payload():
    return {
        "custom_dark_one": "#111111",
        "custom_dark_two": "#222222",
        "custom_dark_three": "#333333",
        "custom_dark_four": "#444444",
        "custom_bg_one": "#555555",
        "custom_bg_two": "#666666",
        "custom_bg_three": "#777777",
        "custom_icon_color": "#888888",
        "custom_icon_hover": "#999999",
        "custom_icon_pressed": "#aaaaaa",
        "custom_icon_active": "#bbbbbb",
        "custom_context_color": "#cccccc",
        "custom_context_hover": "#dddddd",
        "custom_context_pressed": "#eeeeee",
        "custom_text_title": "#f0f0f0",
        "custom_text_foreground": "#0f0f0f",
        "custom_text_description": "#1f1f1f",
        "custom_text_active": "#2f2f2f",
        "custom_white": "#3f3f3f",
        "custom_pink": "#4f4f4f",
        "custom_green": "#5f5f5f",
        "custom_red": "#6f6f6f",
        "custom_yellow": "#7f7f7f",
    }


def test_registry_validates_with_injected_directory(tmp_path):
    class _TmpRegistry(ConfigRegistry):
        pass

    registry = _TmpRegistry()
    registry.THEMES_DIR = str(tmp_path)

    dump_yaml_file(tmp_path / "good.yaml", _valid_theme_payload())
    group = registry.load_themes()

    assert isinstance(group["good"], ConfigFile)
    assert group["good"].data.custom_dark_one == "#111111"

    # 缺必填键 → DomainErrorBoundary(THEME_CONFIG_INVALID)
    broken = _valid_theme_payload()
    broken.pop("custom_dark_two")
    dump_yaml_file(tmp_path / "bad.yaml", broken)
    with pytest.raises(DomainErrorBoundary, match="THEME_CONFIG_INVALID"):
        registry.load_themes()


def test_registry_settings_merge_across_files(tmp_path):
    class _TmpRegistry(ConfigRegistry):
        pass

    registry = _TmpRegistry()
    registry.SETTINGS_DIR = str(tmp_path)

    dump_yaml_file(
        tmp_path / "a.yaml",
        {
            "language": "en_us",
            "theme_name": "bright",
            "logo": "icon",
            "logo_home": "mihoutao",
            "logo_title": "mihoutao",
            "logo_loading": "zig",
            "display": ["banner"],
            "logger_level": "INFO",
            "logger_color": False,
        },
    )
    dump_yaml_file(
        tmp_path / "b.yaml",
        {
            "startup_size": [960, 540],
            "minimum_size": [960, 540],
            "icon_size": 32,
            "custom_title_bar": True,
            "hide_grips": True,
            "window_margin": 2,
            "window_space": 2,
            "window_border_size": 2,
            "window_border_radius": 10,
            "window_shadow": True,
            "lef_menu_size": {"minimum": 50, "maximum": 200},
            "left_menu_content_margins": 2,
            "left_column_size": {"minimum": 0, "maximum": 240},
            "right_column_size": {"minimum": 0, "maximum": 240},
            "right_menu_content_margins": 3,
            "right_title_bar_height": 40,
            "right_content_space": 6,
            "right_credits_height": 40,
            "custom_padding": 10,
            "custom_border": 3,
            "tooltip_border_radius": 17,
            "tooltip_font": 300,
            "time_animation": 500,
            "family": "微软雅黑",
            "title_size": 18,
            "subtitle_size": 15,
            "text_size": 12,
        },
    )

    model = registry.load_settings()

    assert model.theme_name == "bright"
    assert model.family == "微软雅黑"
    assert model.logger_color is False


# ---------------------------------------------------------------------------
# YAML 读写边界
# ---------------------------------------------------------------------------


def test_yaml_file_roundtrip(tmp_path):
    target = tmp_path / "nested" / "demo.yaml"
    payload = {"name": "demo", "items": [1, 2, {"k": "v"}]}

    dump_yaml_file(target, payload)
    assert load_yaml_file(target) == payload


def test_yaml_file_missing_raises_io_boundary(tmp_path):
    with pytest.raises(IOErrorBoundary, match="YAML_FILE_NOT_FOUND"):
        load_yaml_file(tmp_path / "missing.yaml")


def test_yaml_file_parse_error_raises_io_boundary(tmp_path):
    target = tmp_path / "broken.yaml"
    target.write_text("a: [unclosed", encoding="utf-8")

    with pytest.raises(IOErrorBoundary, match="YAML_PARSE_ERROR"):
        load_yaml_file(target)


def test_yaml_handler_dot_path_and_merge(tmp_path):
    target = tmp_path / "cfg.yaml"
    handler = YamlHandler(str(target), auto_load=False)
    handler.set("database.host", "localhost")
    handler.set("database.port", 3306)
    handler.save()

    reloaded = YamlHandler(str(target))
    assert reloaded.get("database.host") == "localhost"
    assert reloaded.get("database.port") == 3306

    extra = YamlHandler(str(tmp_path / "extra.yaml"), auto_load=False)
    extra.set("database.user", "root")
    extra.set("cache.ttl", 60)
    reloaded.merge(extra)
    assert reloaded.database.user == "root"
    assert reloaded.cache.ttl == 60


def test_yaml_handler_root_relative_resolution(tmp_path, monkeypatch):
    # 相对路径始终基于项目根目录解析，与 cwd 无关
    monkeypatch.chdir(tmp_path)
    handler = YamlHandler("resource/customui/settings/config.yaml")

    assert handler.data.language == "zh_cn"
    assert handler.data.theme_name == "default"
