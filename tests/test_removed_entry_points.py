"""历史入口下线守卫：已移除的兼容模块必须不可导入。"""

import pytest

REMOVED_ENTRY_POINTS = [
    "AppCore.SYS.other.folder_tools",
    "AppCore.SYS.module.settings_module",
    "AppCore.SYS.other.resource_locator",
    "AppCore.SYS.locator",
    "AppCore.SYS.loader",
    "AppCore.SYS.logger",
    "Guis.windows.main_window.user_define_window",
]


@pytest.mark.parametrize("module_name", REMOVED_ENTRY_POINTS)
def test_removed_entry_point_import_fails(module_name):
    with pytest.raises(ImportError):
        __import__(module_name)
