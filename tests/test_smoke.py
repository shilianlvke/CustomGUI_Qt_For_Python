"""模块说明。"""

import importlib

import pytest


def test_core_config_smoke() -> None:
    """测试用例：test_core_config_smoke。

    职责:
    - 验证目标行为符合预期。
    """
    appcore = importlib.import_module("AppCore")
    app_languages = appcore.AppLanguages
    app_settings = appcore.AppSettings
    app_themes = appcore.AppThemes

    if not (hasattr(app_settings, "theme_name")):
        pytest.fail("Assertion failed")
    if not (hasattr(app_settings, "language")):
        pytest.fail("Assertion failed")
    if app_settings.theme_name not in app_themes:
        pytest.fail("Assertion failed")
    if app_settings.language not in app_languages:
        pytest.fail("Assertion failed")


def test_public_imports_smoke() -> None:
    """测试用例：test_public_imports_smoke。"""
    appcore = importlib.import_module("AppCore")
    gui = importlib.import_module("gui")
    guicore = importlib.import_module("guicore")

    if not (hasattr(appcore, "Logger")):
        pytest.fail("Assertion failed")
    if not (hasattr(gui, "UiMainWindow")):
        pytest.fail("Assertion failed")
    if not (hasattr(guicore, "Styles")):
        pytest.fail("Assertion failed")


def test_logger_api_smoke() -> None:
    """测试用例：test_logger_api_smoke。"""
    appcore = importlib.import_module("AppCore")
    logger = appcore.Logger

    logger.debug("smoke-debug")
    logger.info("smoke-info")
    logger.warning("smoke-warning")
    logger.error("smoke-error")
    logger.tool("smoke-tool")
