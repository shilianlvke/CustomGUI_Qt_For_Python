import pytest

from AppCore.SYS.handler.yaml_handler import YamlHandler
from AppCore.SYS.module.error_module import (
    DomainErrorBoundary,
    IOErrorBoundary,
    UIErrorBoundary,
    to_user_message,
)


def test_to_user_message_for_app_error():
    err = DomainErrorBoundary(code="DOMAIN_X", message="业务失败", details="detail")

    assert to_user_message(err) == "业务失败 (DOMAIN_X)"


def test_to_user_message_for_unknown_error():
    err = RuntimeError("boom")

    assert "未知错误" in to_user_message(err)


def test_yaml_handler_missing_file_raises_io_boundary():
    with pytest.raises(IOErrorBoundary, match="YAML_FILE_NOT_FOUND"):
        YamlHandler("resource/not_exists.yml")


def test_error_boundary_layers():
    io_err = IOErrorBoundary("IO_X", "io")
    domain_err = DomainErrorBoundary("DOMAIN_X", "domain")
    ui_err = UIErrorBoundary("UI_X", "ui")

    assert io_err.layer == "io"
    assert domain_err.layer == "domain"
    assert ui_err.layer == "ui"