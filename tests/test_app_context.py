from threading import Thread

from sllkgui.appcore import AppSettings, get_app_context


def test_lazy_context_view_access():
    get_app_context(force_reload=True)

    assert hasattr(AppSettings, "theme_name")
    assert isinstance(AppSettings.theme_name, str)


def test_context_reload_returns_loaded_context():
    ctx = get_app_context(force_reload=True)

    assert ctx.settings is not None
    assert ctx.themes is not None
    assert ctx.languages is not None
    assert ctx.others is not None
    assert not hasattr(ctx, "menu")


def test_get_app_context_thread_safe_initialization():
    get_app_context(force_reload=True)
    contexts = []

    def worker():
        contexts.append(get_app_context())

    threads = [Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert contexts
    first = contexts[0]
    assert all(ctx is first for ctx in contexts)


def test_app_context_language_follows_current_language():
    """AppContext.language 跟随 Language.current()，切换语言后立即生效。"""
    # FIX-11: 旧实现回落静态的 AppSettings.language，切语言后读到陈旧值。
    from pathlib import Path

    from sllkgui.appcore import Attrs, Language
    from sllkgui.guis.app_context import AppContext
    from sllkgui.guis.language_service import apply_language

    ctx = AppContext(name="demo", app_dir=Path("."), config=Attrs({}))
    try:
        apply_language("zh_cn")
        assert ctx.language == "zh_cn"
        apply_language("en_us")
        assert ctx.language == "en_us", "language must follow Language.current()"
        assert ctx.language == Language.current()
    finally:
        apply_language("zh_cn")
