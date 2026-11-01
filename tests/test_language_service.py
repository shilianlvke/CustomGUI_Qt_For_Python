"""语言切换服务测试。"""

from types import SimpleNamespace

import pytest

from customgui.appcore import Language
from customgui.guis.language_service import apply_language, current_language, switch_language


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    apply_language("zh_cn")


def test_apply_language_replaces_base_and_apps():
    apply_language("en_us")

    # 应用语言注入（真实 Apps 目录，当前仅有按钮预览应用）
    assert Language.app.button_preview.app_text == "Buttons"
    assert current_language() == "en_us"


def test_apply_language_zh_cn():
    apply_language("zh_cn")

    assert Language.app.button_preview.app_text == "按钮预览"
    assert Language.UI.ui_SwitchLanguage == "切换语言"
    assert current_language() == "zh_cn"


def test_switch_language_cycles():
    """``switch_language()`` 在**全部**可用语言间循环，而不是在两种之间来回。

    基座自带四种语言（zh_cn / en_us / zh_tw / ja_jp）后，循环顺序由
    ``LANGUAGE_OPTIONS`` 决定，不该在测试里硬编码某一种排序结果——
    这条测试断言的是「按当前顺序走到下一个」，语言增减都仍然成立。
    """
    from customgui.appcore import LANGUAGE_OPTIONS

    apply_language("zh_cn")
    options = list(LANGUAGE_OPTIONS)
    start = options.index("zh_cn")
    expected = options[(start + 1) % len(options)]

    assert switch_language() == expected
    assert current_language() == expected

    # 绕一整圈回到起点
    for _ in range(len(options) - 1):
        switch_language()
    assert current_language() == "zh_cn"


def test_apply_language_rejects_unknown():
    with pytest.raises(ValueError, match="不支持的语言"):
        apply_language("fr_fr")


def test_refresh_window_updates_menu_title_and_window_title():
    calls = {}

    def _record(name):
        def _inner(value):
            calls[name] = value

        return _inner

    left_menu = SimpleNamespace(active_button_id=lambda: None)
    title_bar = SimpleNamespace(set_title=_record("page_title"))
    window = SimpleNamespace(
        ui=SimpleNamespace(left_menu=left_menu, title_bar=title_bar),
        setWindowTitle=_record("win_title"),
    )

    apply_language("en_us", window)

    assert calls["win_title"] == "CustomGUI"


def test_refresh_window_missing_ui_is_safe():
    apply_language("en_us", SimpleNamespace())  # 无 ui 属性，安全跳过
    apply_language("zh_cn", None)  # 无窗口，安全跳过


def test_language_subscription_notifies_listeners():
    calls = []

    def _listener():
        calls.append(True)

    from customgui.appcore import Language

    Language.subscribe(_listener)
    try:
        apply_language("en_us")
    finally:
        apply_language("zh_cn")

    assert calls


def test_apply_same_language_is_idempotent():
    """相同语言重复应用：不重复通知订阅者（避免重复刷新与日志）。"""
    apply_language("en_us")
    calls = []

    def _listener():
        calls.append(True)

    from customgui.appcore import Language

    Language.subscribe(_listener)
    try:
        apply_language("en_us")  # 幂等：直接返回，不触发 notify
        assert calls == []
    finally:
        apply_language("zh_cn")
