"""语言切换服务测试。"""

from types import SimpleNamespace

import pytest

from sllkgui.appcore import Language
from sllkgui.guis import language_service
from sllkgui.guis.language_service import apply_language, current_language, switch_language


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    apply_language("zh_cn")


def test_apply_language_replaces_base():
    apply_language("en_us")

    assert current_language() == "en_us"


def test_apply_language_zh_cn():
    apply_language("zh_cn")

    assert Language.UI.ui_SwitchLanguage == "切换语言"
    assert current_language() == "zh_cn"


def test_switch_language_cycles():
    """``switch_language()`` 在**全部**可用语言间循环，而不是在两种之间来回。

    基座自带四种语言（zh_cn / en_us / zh_tw / ja_jp）后，循环顺序由
    ``LANGUAGE_OPTIONS`` 决定，不该在测试里硬编码某一种排序结果——
    这条测试断言的是「按当前顺序走到下一个」，语言增减都仍然成立。
    """
    from sllkgui.appcore import LANGUAGE_OPTIONS

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

    assert calls["win_title"] == "SllkGUI"


def test_refresh_window_missing_ui_is_safe():
    apply_language("en_us", SimpleNamespace())  # 无 ui 属性，安全跳过
    apply_language("zh_cn", None)  # 无窗口，安全跳过


def test_language_subscription_notifies_listeners():
    calls = []

    def _listener():
        calls.append(True)

    from sllkgui.appcore import Language

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

    from sllkgui.appcore import Language

    Language.subscribe(_listener)
    try:
        apply_language("en_us")  # 幂等：直接返回，不触发 notify
        assert calls == []
    finally:
        apply_language("zh_cn")


def test_all_pages_with_retranslate_skip_rebuild(qapp):
    """所有已加载页面都实现 retranslate() 时只局部刷新，不重建页面栈。"""
    from PySide6.QtWidgets import QStackedWidget, QWidget

    calls = []
    pages = QStackedWidget()
    first = QWidget()
    first.setObjectName("home_page")
    first.retranslate = lambda: calls.append("home_page")
    second = QWidget()
    second.setObjectName("settings_page")
    second.retranslate = lambda: calls.append("settings_page")
    pages.addWidget(first)
    pages.addWidget(second)
    pages.setCurrentWidget(first)

    titles = {}
    window = SimpleNamespace(
        ui=SimpleNamespace(
            load_pages=SimpleNamespace(pages=pages),
            left_menu=SimpleNamespace(active_button_id=lambda: None),
            title_bar=SimpleNamespace(set_title=lambda text: titles.update(page=text)),
        ),
        setWindowTitle=lambda text: titles.update(window=text),
    )

    apply_language("en_us", window)

    assert pages.count() == 2
    assert pages.widget(0) is first
    assert pages.widget(1) is second
    assert calls == ["home_page", "settings_page"]
    assert titles["window"] == Language.custom_ui.sys_name


def test_scroll_positions_survive_page_rebuild(qapp, monkeypatch):
    """整页重建路径下，QScrollArea 的滚动位置按稳定键恢复。"""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea, QStackedWidget, QVBoxLayout, QWidget

    from sllkgui.guicore import CScrollArea
    from sllkgui.guis import language_service
    from sllkgui.guis.windows.main_window import registry

    stack = QStackedWidget()
    stack.resize(400, 300)
    stack.show()

    def _build_page():
        page = QWidget()
        page.setObjectName("home_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        area = CScrollArea(object_name="page_scroll")
        content = QWidget()
        content.setMinimumHeight(1200)
        area.setWidget(content)
        layout.addWidget(area)
        return page, area

    page, area = _build_page()
    stack.addWidget(page)
    stack.setCurrentWidget(page)
    QTest.qWait(30)
    area.verticalScrollBar().setValue(500)
    assert area.verticalScrollBar().value() == 500

    def _load_registered_pages(_window, eager=False):
        rebuilt_page, _rebuilt_area = _build_page()
        stack.addWidget(rebuilt_page)

    monkeypatch.setattr(registry, "load_registered_pages", _load_registered_pages)
    monkeypatch.setattr(registry, "ensure_registered_page", lambda *args, **kwargs: False)
    monkeypatch.setattr(registry, "get_page_routes", lambda _language: {"btn_home": ("home_page", "Home")})
    monkeypatch.setattr(registry, "get_default_page_object", lambda: "home_page")

    window = SimpleNamespace(
        ui=SimpleNamespace(
            load_pages=SimpleNamespace(pages=stack),
            left_menu=SimpleNamespace(active_button_id=lambda: "btn_home"),
        )
    )
    language_service._rebuild_pages(window)

    rebuilt = stack.currentWidget()
    assert rebuilt is not page
    new_area = rebuilt.findChild(QScrollArea, "page_scroll")
    assert new_area is not None
    assert new_area.verticalScrollBar().value() == 500
    stack.close()


# ==========================================================================
# FIX-11：占位页、retranslateUi 适配、失败回滚、v2 生命周期钩子
# ==========================================================================
def test_placeholder_pages_do_not_block_retranslate(qapp):
    """占位 QWidget 不阻断局部刷新：跳过两个占位页后只对真实页面重翻译。"""
    # FIX-11: Main_Page / widget_show 不是应用页面且永远没有 retranslate()，必须跳过。
    from PySide6.QtWidgets import QStackedWidget, QWidget

    calls = []
    pages = QStackedWidget()
    for name in ("Main_Page", "widget_show"):
        placeholder = QWidget()
        placeholder.setObjectName(name)
        placeholder.retranslate = lambda: calls.append("placeholder")
        pages.addWidget(placeholder)
    real = QWidget()
    real.setObjectName("home_page")
    real.retranslate = lambda: calls.append("home_page")
    pages.addWidget(real)

    window = SimpleNamespace(ui=SimpleNamespace(load_pages=SimpleNamespace(pages=pages)))

    assert language_service._retranslate_pages(window) is True
    assert calls == ["home_page"], "placeholder pages must be skipped"

    # 跳过占位页后没有任何真实页面时，仍回退整页重建
    only_placeholders = QStackedWidget()
    placeholder = QWidget()
    placeholder.setObjectName("Main_Page")
    only_placeholders.addWidget(placeholder)
    empty_window = SimpleNamespace(ui=SimpleNamespace(load_pages=SimpleNamespace(pages=only_placeholders)))
    assert language_service._retranslate_pages(empty_window) is False


def test_retranslateui_adapter_is_invoked(qapp):
    """实现了 retranslateUi(widget) 的页面也能走局部刷新。"""
    # FIX-11: uic 生成的方法带一个参数，适配层须把页面自身传进去；无参形式也要兜底。
    from PySide6.QtWidgets import QStackedWidget, QWidget

    calls = []
    pages = QStackedWidget()
    with_arg = QWidget()
    with_arg.setObjectName("page_home")
    with_arg.retranslateUi = lambda widget: calls.append(widget)
    no_arg = QWidget()
    no_arg.setObjectName("page_settings")
    no_arg.retranslateUi = lambda: calls.append("no_arg")
    pages.addWidget(with_arg)
    pages.addWidget(no_arg)

    window = SimpleNamespace(ui=SimpleNamespace(load_pages=SimpleNamespace(pages=pages)))

    assert language_service._retranslate_pages(window) is True
    assert calls == [with_arg, "no_arg"], "retranslateUi adapter must handle both signatures"


def test_apply_language_rolls_back_user_settings_on_refresh_failure(monkeypatch):
    """窗口刷新失败时回滚语言、不写 user.yaml，并返回旧语言名。"""
    # FIX-11: 旧实现无论刷新成败都无条件写 user.yaml，重启会恢复到未生效的语言。
    apply_language("zh_cn")
    saved = []

    def _boom(_window):
        raise RuntimeError("refresh boom")

    monkeypatch.setattr(language_service, "_refresh_window", _boom)
    monkeypatch.setattr(language_service, "save_user_settings", lambda **kwargs: saved.append(kwargs))
    try:
        result = apply_language("en_us", window=object())
        assert result == "zh_cn", "failure must return the previous language"
        assert Language.current() == "zh_cn", "language must roll back on refresh failure"
        assert saved == [], "user.yaml must not be written on refresh failure"
    finally:
        apply_language("zh_cn")


def test_language_hooks_are_invoked(monkeypatch):
    """语言切换成功后调用 Gallery 插件的 on_locale_changed，单个钩子失败被隔离。"""
    import sllkgui.gallery.registry as gallery_registry

    calls = []

    class _Plugin:
        def on_locale_changed(self, language):
            calls.append(language)

    class _BoomPlugin:
        def on_locale_changed(self, language):
            raise RuntimeError("hook boom")

    class _Registry:
        def plugins(self):
            return [
                SimpleNamespace(plugin_id="boom", plugin=_BoomPlugin()),
                SimpleNamespace(plugin_id="ok", plugin=_Plugin()),
            ]

    monkeypatch.setattr(gallery_registry, "current_registry", lambda: _Registry())
    try:
        result = apply_language("en_us")
        assert result == "en_us", "a failing hook must not break the switch"
        assert calls == ["en_us"], "on_locale_changed must be invoked on success"
    finally:
        apply_language("zh_cn")
