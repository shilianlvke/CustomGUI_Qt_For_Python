import pytest


def test_canonical_language_module_imports():
    from AppCore.SYS.module.language_module import Language, LanguageHandler

    assert Language is not None
    assert LanguageHandler is not None


def test_legacy_language_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        from AppCore.SYS.module.languge_module import Language  # noqa: F401


def test_canonical_loading_ui_module_imports():
    from GUI.windows.loading_window.ui_main import LoadingWindow

    assert LoadingWindow is not None


def test_legacy_loading_ui_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        from GUI.windows.loading_window.ui_mian import LoadingWindow  # noqa: F401
