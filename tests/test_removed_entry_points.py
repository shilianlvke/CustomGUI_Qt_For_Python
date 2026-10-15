"""历史入口下线守卫：已移除的兼容模块/符号必须不可导入或不存在。"""

import pytest

REMOVED_ENTRY_POINTS = [
    "AppCore.SYS.other.folder_tools",
    "AppCore.SYS.module.settings_module",
    "AppCore.SYS.other.resource_locator",
    "AppCore.SYS.locator",
    "AppCore.SYS.loader",
    "AppCore.SYS.logger",
    "AppCore.SYS.handler.json_handler",
    "Guis.windows.main_window.user_define_window",
    "Guis.windows.main_window.user_define_pages",
]

# 已下线的公开符号：(模块, 符号名)
REMOVED_SYMBOLS = [
    # initialize_app_context 与 get_app_context 完全等价，已下线
    ("AppCore", "initialize_app_context"),
    ("AppCore.SYS.config.registry", "initialize_app_context"),
    # JsonHandler 零消费者，已随 json_handler 模块一并下线
    ("AppCore", "JsonHandler"),
    ("AppCore.SYS.handler", "JsonHandler"),
    # AppContext 在 config 包内已更名为 ConfigContext，避免与 Guis.app_loader.AppContext 重名
    ("AppCore.SYS.config.registry", "AppContext"),
]


@pytest.mark.parametrize("module_name", REMOVED_ENTRY_POINTS)
def test_removed_entry_point_import_fails(module_name):
    with pytest.raises(ImportError):
        __import__(module_name)


@pytest.mark.parametrize("module_name,symbol", REMOVED_SYMBOLS)
def test_removed_public_symbol_is_absent(module_name, symbol):
    module = __import__(module_name, fromlist=[symbol])
    assert not hasattr(module, symbol), f"{module_name}.{symbol} 应已下线"
