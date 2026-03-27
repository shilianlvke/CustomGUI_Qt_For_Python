"""模块说明。"""

import pytest

from AppCore.SYS.handler.yaml_handler import YamlHandler
from AppCore.SYS.module.error_module import (
    DomainErrorBoundary,
    IOErrorBoundary,
    UIErrorBoundary,
    to_user_message,
)


def test_to_user_message_for_app_error() -> None:
    """测试用例：test_to_user_message_for_app_error。

    职责:
    - 验证目标行为符合预期。
    """
    err = DomainErrorBoundary(code="DOMAIN_X", message="业务失败", details="detail")

    if to_user_message(err) != "业务失败 (DOMAIN_X)":
        pytest.fail("Assertion failed")


def test_to_user_message_for_unknown_error() -> None:
    """测试用例：test_to_user_message_for_unknown_error。"""
    err = RuntimeError("boom")

    if "未知错误" not in to_user_message(err):
        pytest.fail("Assertion failed")


def test_yaml_handler_missing_file_raises_io_boundary() -> None:
    """测试用例：test_yaml_handler_missing_file_raises_io_boundary。"""
    with pytest.raises(IOErrorBoundary, match="YAML_FILE_NOT_FOUND"):
        YamlHandler("resource/not_exists.yml")


def test_error_boundary_layers() -> None:
    """测试用例：test_error_boundary_layers。"""
    io_err = IOErrorBoundary("IO_X", "io")
    domain_err = DomainErrorBoundary("DOMAIN_X", "domain")
    ui_err = UIErrorBoundary("UI_X", "ui")

    if io_err.layer != "io":
        pytest.fail("Assertion failed")
    if domain_err.layer != "domain":
        pytest.fail("Assertion failed")
    if ui_err.layer != "ui":
        pytest.fail("Assertion failed")
