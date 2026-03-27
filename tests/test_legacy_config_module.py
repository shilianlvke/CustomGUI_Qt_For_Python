"""模块说明。"""

import importlib

import pytest


def test_legacy_config_module_is_removed_from_package_import() -> None:
    """测试用例：test_legacy_config_module_is_removed_from_package_import。

    职责:
    - 验证目标行为符合预期。
    """
    with pytest.raises(ImportError):
        importlib.import_module("AppCore.SYS.module.config_module")


def test_legacy_config_module_is_removed_from_direct_import() -> None:
    """测试用例：test_legacy_config_module_is_removed_from_direct_import。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("AppCore.SYS.module.config_module")
