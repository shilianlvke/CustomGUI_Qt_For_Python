"""模块说明。"""

import importlib

import pytest


def test_canonical_language_module_imports() -> None:
    """测试用例：test_canonical_language_module_imports。

    职责:
    - 验证目标行为符合预期。
    """
    language_module = importlib.import_module("AppCore.SYS.module.language_module")

    if not (language_module.Language is not None):
        pytest.fail("Assertion failed")
    if not (language_module.LanguageHandler is not None):
        pytest.fail("Assertion failed")


def test_legacy_language_module_is_removed() -> None:
    """测试用例：test_legacy_language_module_is_removed。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("AppCore.SYS.module.languge_module")


def test_canonical_loading_ui_module_imports() -> None:
    """测试用例：test_canonical_loading_ui_module_imports。"""
    ui_module = importlib.import_module("gui.windows.loading_window.ui_main")

    if not (ui_module.LoadingWindow is not None):
        pytest.fail("Assertion failed")


def test_legacy_loading_ui_module_is_removed() -> None:
    """测试用例：test_legacy_loading_ui_module_is_removed。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gui.windows.loading_window.ui_mian")
