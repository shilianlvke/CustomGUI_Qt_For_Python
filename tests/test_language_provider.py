"""语言提供者列表合并测试：register_app_provider 支持多来源。"""

from __future__ import annotations

import pytest

from sllkgui.appcore import Language
from sllkgui.appcore.sysx.modules.language_module import LanguageHandler


@pytest.fixture()
def handler():
    """独立的 LanguageHandler，避免污染全局 Language 单例。"""
    return LanguageHandler()


def test_multiple_providers_merge(handler):
    handler.register_app_provider(lambda lang: {"app_a": {"text": "A"}, "shared": {"k": "first"}})
    handler.register_app_provider(lambda lang: {"app_b": {"text": "B"}, "shared": {"k": "second"}})

    merged = handler._collect_app_languages("zh_cn")

    assert merged["app_a"] == {"text": "A"}
    assert merged["app_b"] == {"text": "B"}
    # 后注册的覆盖同名键
    assert merged["shared"] == {"k": "second"}


def test_duplicate_provider_not_registered_twice(handler):
    provider = lambda lang: {"app": {"x": "1"}}  # noqa: E731

    handler.register_app_provider(provider)
    handler.register_app_provider(provider)

    assert len(handler._app_providers) == 1


def test_failing_provider_does_not_block_others(handler):
    def good(lang):
        return {"app": {"ok": "1"}}

    def bad(lang):
        raise RuntimeError("boom")

    handler.register_app_provider(good)
    handler.register_app_provider(bad)

    merged = handler._collect_app_languages("zh_cn")
    assert merged == {"app": {"ok": "1"}}


def test_non_dict_result_is_ignored(handler):
    handler.register_app_provider(lambda lang: "not a dict")
    handler.register_app_provider(lambda lang: {"app": {"ok": "1"}})

    merged = handler._collect_app_languages("zh_cn")
    assert merged == {"app": {"ok": "1"}}


def test_apply_injects_merged_app_languages(handler):
    """``apply()`` 用合并后的结果填充 ``Language.app``。"""
    handler.register_app_provider(lambda lang: {"app_a": {"text": "甲"}})
    handler.register_app_provider(lambda lang: {"app_b": {"text": "乙"}})

    handler.apply("zh_cn")

    assert handler.app.app_a.text == "甲"
    assert handler.app.app_b.text == "乙"


def test_global_language_singleton_still_works():
    """全局单例在注册 provider 后正常切换（回归门禁）。"""
    original = Language.current()
    try:
        Language.apply("zh_cn")
        assert Language.current() == "zh_cn"
    finally:
        Language.apply(original)


def test_resolve_flat_surface_title_for_dotted_plugin_id(handler):
    """插件菜单键：扁平标题键 + 反向域名插件 id 应按 4 种语言解析。"""
    titles = {"zh_cn": "小部件", "zh_tw": "小工具", "en_us": "Widgets", "ja_jp": "ウィジェット"}
    handler.register_app_provider(
        lambda lang: {"com.example.hello": {"surface.home.title": titles.get(lang, titles["en_us"])}}
    )

    for language in ("zh_cn", "zh_tw", "en_us", "ja_jp"):
        handler.apply(language)
        assert handler.resolve("app.com.example.hello.surface.home.title", "MISS") == titles[language]
        key = "language.app.com.example.hello.surface.home.title"
        assert handler.resolve_key(key, "MISS") == titles[language]


def test_resolve_nested_app_text_still_works(handler):
    """嵌套命名空间（不带点）的原有解析行为不能回归。"""
    handler.register_app_provider(lambda lang: {"example": {"page": {"title": "标题"}}})
    handler.apply("zh_cn")
    assert handler.resolve("app.example.page.title") == "标题"
