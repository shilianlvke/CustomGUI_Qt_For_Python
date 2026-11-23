"""P1 重复逻辑抽取：共享展示文本与配置兜底工具。"""

from __future__ import annotations

import pytest

from sllkgui.appcore.settings import schema as schema_module
from sllkgui.appcore.settings.schema import (
    Setting,
    SettingsAction,
    SettingsInfo,
    SettingsPage,
    SettingsSection,
    _display_text,
)
from sllkgui.guicore.custom_ui.config_helpers import resolve_config


class _FakeLanguage:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve_key(self, key, default):
        self.calls.append((key, default))
        return self.result if self.result is not None else default


def _patch_language(monkeypatch, result):
    fake = _FakeLanguage(result)
    monkeypatch.setattr("sllkgui.appcore.sysx.modules.language_module.Language", fake)
    return fake


def test_display_text_without_key_returns_fallback(monkeypatch):
    fake = _patch_language(monkeypatch, "translated")
    assert _display_text("", "回退文本") == "回退文本"
    assert fake.calls == []  # 无语言键时不触碰语言服务


def test_display_text_with_key_resolves_language(monkeypatch):
    fake = _patch_language(monkeypatch, "Translated")
    assert _display_text("language.app.some_key", "回退文本") == "Translated"
    assert fake.calls == [("language.app.some_key", "回退文本")]


def test_display_text_with_key_uses_fallback_when_resolution_returns_none(monkeypatch):
    _patch_language(monkeypatch, None)
    assert _display_text("language.app.missing", "回退文本") == "回退文本"


def test_display_text_with_non_string_result_is_stringified(monkeypatch):
    _patch_language(monkeypatch, 123)
    assert _display_text("language.app.number", "fallback") == "123"


def test_schema_display_methods_delegate_to_helper(monkeypatch):
    """各 display_* 的 fallback 与调用契约保持不变。"""
    fake = _patch_language(monkeypatch, "译")

    option = schema_module.SettingOption(value="v", label="L", label_key="language.k1")
    assert option.display_label() == "译"
    assert fake.calls[-1] == ("language.k1", "L")

    action = SettingsAction(
        key="act",
        label="A",
        hint="H",
        button="B",
        label_key="language.k2",
        hint_key="language.k3",
        button_key="language.k4",
    )
    assert action.display_label() == "译"
    assert fake.calls[-1] == ("language.k2", "A")
    assert action.display_hint() == "译"
    assert fake.calls[-1] == ("language.k3", "H")
    assert action.display_button() == "译"
    assert fake.calls[-1] == ("language.k4", "B")

    info = SettingsInfo(key="i", label="I", hint="IH", hint_key="language.k5")
    assert info.display_hint() == "译"
    assert fake.calls[-1] == ("language.k5", "IH")

    spec = Setting.switch("s", True, "S", hint="SH", hint_key="language.k6")
    assert spec.display_label() == "S"  # 无 label_key 直接回落
    assert spec.display_hint() == "译"
    assert fake.calls[-1] == ("language.k6", "SH")

    section = SettingsSection("T", title_key="language.k7", hint_key="language.k8", hint="SECH")
    assert section.display_title() == "译"
    assert fake.calls[-1] == ("language.k7", "T")
    assert section.display_hint() == "译"
    assert fake.calls[-1] == ("language.k8", "SECH")

    page = SettingsPage(page_id="p", title="PT", title_key="language.k9")
    assert page.display_title() == "译"
    assert fake.calls[-1] == ("language.k9", "PT")


def test_resolve_config_converts_values_by_default_types():
    defaults = (1, 2, 0.5)
    result = resolve_config(lambda: ("4", "5", "1.25"), defaults)
    assert result == (4, 5, 1.25)
    assert isinstance(result[0], int) and isinstance(result[1], int)
    assert isinstance(result[2], float)


def test_resolve_config_preserves_non_numeric_defaults():
    assert resolve_config(lambda: ("x", True), ("", False)) == ("x", True)


def test_resolve_config_returns_defaults_on_getter_error():
    def broken_getter():
        raise RuntimeError("config context not ready")

    defaults = (4, 8, 0.38)
    assert resolve_config(broken_getter, defaults) is defaults


def test_resolve_config_returns_defaults_on_conversion_error():
    defaults = (4, 8)
    assert resolve_config(lambda: ("oops", "8"), defaults) is defaults


@pytest.mark.parametrize(
    "module_name,fn_name",
    [
        ("sllkgui.guicore.custom_ui.button.button", "_button_config"),
        ("sllkgui.guicore.custom_ui.button.split_button", "_split_button_config"),
        ("sllkgui.guicore.custom_ui.menu.mega_menu", "_mega_menu_config"),
    ],
)
def test_component_config_uses_shared_helper_on_error(monkeypatch, module_name, fn_name, qapp):
    """配置上下文抛错时三个组件都通过共享 helper 回落默认值。"""
    import importlib

    module = importlib.import_module(module_name)
    config_fn = getattr(module, fn_name)
    defaults = config_fn()  # 当前上下文下的合法值，作为对照

    class _BrokenSettings:
        def __getattr__(self, name):
            raise RuntimeError("not ready")

    monkeypatch.setattr(module, "AppSettings", _BrokenSettings())
    assert config_fn() == defaults
