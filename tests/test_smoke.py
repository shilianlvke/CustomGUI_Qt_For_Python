"""模块说明。"""

import importlib


def test_core_config_smoke() -> None:
    """测试用例：test_core_config_smoke。

    职责:
    - 验证目标行为符合预期。
    """
    appcore = importlib.import_module("AppCore")
    app_languages = appcore.AppLanguages
    app_settings = appcore.AppSettings
    app_themes = appcore.AppThemes

    assert hasattr(app_settings, "theme_name")
    assert hasattr(app_settings, "language")
    assert app_settings.theme_name in app_themes
    assert app_settings.language in app_languages


def test_public_imports_smoke() -> None:
    """测试用例：test_public_imports_smoke。"""
    appcore = importlib.import_module("AppCore")
    gui = importlib.import_module("GUI")
    guicore = importlib.import_module("GuiCore")

    assert hasattr(appcore, "Logger")
    assert hasattr(gui, "UiMainWindow")
    assert hasattr(guicore, "Styles")


def test_logger_api_smoke() -> None:
    """测试用例：test_logger_api_smoke。"""
    appcore = importlib.import_module("AppCore")
    logger = appcore.Logger

    logger.debug("smoke-debug")
    logger.info("smoke-info")
    logger.warning("smoke-warning")
    logger.error("smoke-error")
    logger.tool("smoke-tool")
