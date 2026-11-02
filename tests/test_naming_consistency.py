import pytest


def test_canonical_language_module_imports():
    from customgui.appcore.sysx.modules.language_module import Language, LanguageHandler

    assert Language is not None
    assert LanguageHandler is not None


def test_legacy_language_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        from customgui.appcore.sysx.modules.languge_module import Language  # noqa: F401
