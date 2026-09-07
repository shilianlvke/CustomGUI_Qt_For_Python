"""模块说明。"""

import importlib

import pytest


def test_canonical_token_manager_imports() -> None:
    """测试用例：test_canonical_token_manager_imports。

    职责:
    - 验证令牌管理器规范入口存在。
    """
    token_manager_module = importlib.import_module("AppCore.system.other.token_manager")

    if not (token_manager_module.TokenManager is not None):
        pytest.fail("Assertion failed")
    if not (token_manager_module.get_token_manager is not None):
        pytest.fail("Assertion failed")


def test_legacy_language_module_is_removed() -> None:
    """测试用例：test_legacy_language_module_is_removed。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("AppCore.system.module.languge_module")


def test_canonical_loading_ui_module_imports() -> None:
    """测试用例：test_canonical_loading_ui_module_imports。"""
    ui_module = importlib.import_module("gui.windows.loading_window.ui_main")

    if not (ui_module.LoadingWindow is not None):
        pytest.fail("Assertion failed")


def test_legacy_loading_ui_module_is_removed() -> None:
    """测试用例：test_legacy_loading_ui_module_is_removed。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gui.windows.loading_window.ui_mian")
