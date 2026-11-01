def test_core_config_smoke():
    from customgui.appcore import AppLanguages, AppSettings, AppThemes

    assert hasattr(AppSettings, "theme_name")
    assert hasattr(AppSettings, "language")
    assert AppSettings.theme_name in AppThemes
    assert AppSettings.language in AppLanguages


def test_public_imports_smoke():
    import customgui.appcore
    import customgui.guicore
    import customgui.guis

    assert hasattr(customgui.appcore, "Logger")
    assert hasattr(customgui.guis, "UiMainWindow")
    assert hasattr(customgui.guicore, "Styles")


def test_logger_api_smoke():
    from customgui.appcore import Logger

    Logger.debug("smoke-debug")
    Logger.info("smoke-info")
    Logger.warning("smoke-warning")
    Logger.error("smoke-error")
    Logger.tool("smoke-tool")
