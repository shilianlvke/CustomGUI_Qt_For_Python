def test_core_config_smoke():
    from sllkgui.appcore import AppLanguages, AppSettings, AppThemes

    assert hasattr(AppSettings, "theme_name")
    assert hasattr(AppSettings, "language")
    assert AppSettings.theme_name in AppThemes
    assert AppSettings.language in AppLanguages


def test_public_imports_smoke():
    import sllkgui.appcore
    import sllkgui.guicore
    import sllkgui.guis

    assert hasattr(sllkgui.appcore, "Logger")
    assert hasattr(sllkgui.guis, "UiMainWindow")
    assert hasattr(sllkgui.guicore, "Styles")


def test_logger_api_smoke():
    from sllkgui.appcore import Logger

    Logger.debug("smoke-debug")
    Logger.info("smoke-info")
    Logger.warning("smoke-warning")
    Logger.error("smoke-error")
    Logger.tool("smoke-tool")
