"""语言切换服务测试。"""

from types import SimpleNamespace

import pytest

from AppCore import Language
from Guis.language_service import apply_language, current_language, switch_language


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    apply_language("zh_cn")


def test_apply_language_replaces_base_and_apps():
    apply_language("en_us")

    assert Language.PAGE.widget_show.title == "Component Showcase"
    # 应用语言注入（真实 Apps 目录）
    assert Language.app.p2ptest_home.app_text == "P2PTester"
    assert Language.app.example.app_tooltip == "this is a plugin's example...."
    assert current_language() == "en_us"


def test_apply_language_zh_cn():
    apply_language("zh_cn")

    assert Language.PAGE.widget_show.title == "组件展示"
    assert Language.app.example.app_text == "示例插件"
    assert Language.UI.ui_SwitchLanguage == "切换语言"
    assert current_language() == "zh_cn"


def test_switch_language_cycles():
    apply_language("zh_cn")

    assert switch_language() == "en_us"
    assert Language.UI.ui_SwitchLanguage == "Switch Language"
    assert switch_language() == "zh_cn"
    assert Language.UI.ui_SwitchLanguage == "切换语言"


def test_apply_language_rejects_unknown():
    with pytest.raises(ValueError, match="不支持的语言"):
        apply_language("fr_fr")


def test_refresh_window_updates_menu_title_and_window_title():
    calls = {}

    def _record(name):
        def _inner(value):
            calls[name] = value

        return _inner

    left_menu = SimpleNamespace(
        apply_language=_record("left"),
        active_button_id=lambda: None,
    )
    title_bar = SimpleNamespace(
        apply_language=_record("title_bar"),
        set_title=_record("page_title"),
    )
    window = SimpleNamespace(
        ui=SimpleNamespace(left_menu=left_menu, title_bar=title_bar),
        setWindowTitle=_record("win_title"),
    )

    apply_language("en_us", window)

    assert calls["win_title"] == "P2PTester"
    assert callable(calls["left"])
    assert callable(calls["title_bar"])


def test_refresh_window_missing_ui_is_safe():
    apply_language("en_us", SimpleNamespace())  # 无 ui 属性，安全跳过
    apply_language("zh_cn", None)  # 无窗口，安全跳过
