"""历史入口下线守卫：已移除的兼容模块/符号必须不可导入或不存在。"""

import pytest

REMOVED_ENTRY_POINTS = [
    "sllkgui.appcore.sysx.common.folder_tools",
    "sllkgui.appcore.sysx.modules.settings_module",
    "sllkgui.appcore.sysx.common.resource_locator",
    "sllkgui.appcore.sysx.locator",
    "sllkgui.appcore.sysx.loader",
    "sllkgui.appcore.sysx.logger",
    "sllkgui.appcore.sysx.handlers.json_handler",
    "sllkgui.guis.windows.main_window.user_define_window",
    "sllkgui.guis.windows.main_window.user_define_pages",
    # Windows 设备探测（串口/HID/网卡）与校验算法不属于基座：它们会拖入
    # pyserial/hidapi/wmi 三个可选依赖，而基座一个都不需要。应用要就自己在
    # 自己的 core 目录里实现。
    "sllkgui.appcore.tool.device",
    "sllkgui.appcore.tool.Net",
    "sllkgui.appcore.tool.verify",
]

# 已下线的公开符号：(模块, 符号名)
REMOVED_SYMBOLS = [
    # initialize_app_context 与 get_app_context 完全等价，已下线
    ("sllkgui.appcore", "initialize_app_context"),
    ("sllkgui.appcore.sysx.config.registry", "initialize_app_context"),
    # JsonHandler 零消费者，已随 json_handler 模块一并下线
    ("sllkgui.appcore", "JsonHandler"),
    ("sllkgui.appcore.sysx.handlers", "JsonHandler"),
    # AppContext 在 config 包内已更名为 ConfigContext，避免与 sllkgui.guis.app_loader.AppContext 重名
    ("sllkgui.appcore.sysx.config.registry", "AppContext"),
]


@pytest.mark.parametrize("module_name", REMOVED_ENTRY_POINTS)
def test_removed_entry_point_import_fails(module_name):
    with pytest.raises(ImportError):
        __import__(module_name)


@pytest.mark.parametrize("module_name,symbol", REMOVED_SYMBOLS)
def test_removed_public_symbol_is_absent(module_name, symbol):
    module = __import__(module_name, fromlist=[symbol])
    assert not hasattr(module, symbol), f"{module_name}.{symbol} 应已下线"
