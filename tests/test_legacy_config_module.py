import pytest


def test_legacy_config_module_is_removed_from_package_import():
    """测试用例：test_legacy_config_module_is_removed_from_package_import。

    职责:
    - 验证目标行为符合预期。
    """
    with pytest.raises(ImportError):
        from AppCore.SYS.module import config_module  # noqa: F401


def test_legacy_config_module_is_removed_from_direct_import():
    "测试用例：test_legacy_config_module_is_removed_from_direct_import。"
    with pytest.raises(ModuleNotFoundError):
        from AppCore.SYS.module.config_module import AppSettings  # noqa: F401

