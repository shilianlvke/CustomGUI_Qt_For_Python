"""历史入口下线守卫：已移除的兼容模块/符号必须不可导入或不存在。"""

import pytest

REMOVED_ENTRY_POINTS = [
    "customgui.appcore.sysx.common.folder_tools",
    "customgui.appcore.sysx.modules.settings_module",
    "customgui.appcore.sysx.common.resource_locator",
    "customgui.appcore.sysx.locator",
    "customgui.appcore.sysx.loader",
    "customgui.appcore.sysx.logger",
    "customgui.appcore.sysx.handlers.json_handler",
    "customgui.guis.windows.main_window.user_define_window",
    "customgui.guis.windows.main_window.user_define_pages",
]

# 已下线的公开符号：(模块, 符号名)
REMOVED_SYMBOLS = [
    # initialize_app_context 与 get_app_context 完全等价，已下线
    ("customgui.appcore", "initialize_app_context"),
    ("customgui.appcore.sysx.config.registry", "initialize_app_context"),
    # JsonHandler 零消费者，已随 json_handler 模块一并下线
    ("customgui.appcore", "JsonHandler"),
    ("customgui.appcore.sysx.handlers", "JsonHandler"),
    # AppContext 在 config 包内已更名为 ConfigContext，避免与 customgui.guis.app_loader.AppContext 重名
    ("customgui.appcore.sysx.config.registry", "AppContext"),
]


@pytest.mark.parametrize("module_name", REMOVED_ENTRY_POINTS)
def test_removed_entry_point_import_fails(module_name):
    with pytest.raises(ImportError):
        __import__(module_name)


@pytest.mark.parametrize("module_name,symbol", REMOVED_SYMBOLS)
def test_removed_public_symbol_is_absent(module_name, symbol):
    module = __import__(module_name, fromlist=[symbol])
    assert not hasattr(module, symbol), f"{module_name}.{symbol} 应已下线"
