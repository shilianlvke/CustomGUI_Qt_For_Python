import pytest


def test_legacy_config_module_is_removed_from_package_import():
    with pytest.raises(ImportError):
        from customgui.appcore.sysx.modules import config_module  # noqa: F401


def test_legacy_config_module_is_removed_from_direct_import():
    with pytest.raises(ModuleNotFoundError):
        from customgui.appcore.sysx.modules.config_module import AppSettings  # noqa: F401
