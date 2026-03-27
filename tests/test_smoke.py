def test_core_config_smoke():
    """测试用例：test_core_config_smoke。

    职责:
    - 验证目标行为符合预期。
    """
    from AppCore import AppLanguages, AppSettings, AppThemes

    assert hasattr(AppSettings, "theme_name")
    assert hasattr(AppSettings, "language")
    assert AppSettings.theme_name in AppThemes
    assert AppSettings.language in AppLanguages


def test_public_imports_smoke():
    "测试用例：test_public_imports_smoke。"
    import AppCore
    import GUI
    import GuiCore

    assert hasattr(AppCore, "Logger")
    assert hasattr(GUI, "UiMainWindow")
    assert hasattr(GuiCore, "Styles")


def test_logger_api_smoke():
    "测试用例：test_logger_api_smoke。"
    from AppCore import Logger

    Logger.debug("smoke-debug")
    Logger.info("smoke-info")
    Logger.warning("smoke-warning")
    Logger.error("smoke-error")
    Logger.tool("smoke-tool")

