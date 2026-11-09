import pytest

from sllkgui.appcore.sysx.handlers.yaml_handler import YamlHandler
from sllkgui.appcore.sysx.modules.error_module import (
    AppError,
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


def test_app_error_args_are_populated():
    """FIX-08: AppError 补 Exception.__init__ 后 args 非空，且 __str__ 契约不变。"""
    # FIX-08: 三个子类的关键字 super().__init__ 调用与 AppError 直接构造均须生效。
    io_err = IOErrorBoundary(code="IO_X", message="io 失败", details="d1")
    domain_err = DomainErrorBoundary(code="DOMAIN_X", message="domain 失败")
    ui_err = UIErrorBoundary(code="UI_X", message="ui 失败")
    app_err = AppError(code="APP_X", message="app 失败", layer="app", details="d2")

    for err in (io_err, domain_err, ui_err, app_err):
        assert err.args, "AppError.args must not be empty"

    assert io_err.args == ("io 失败",), "args must carry the message"
    assert str(io_err) == "[io:IO_X] io 失败 (d1)", "__str__ format must stay unchanged"
    assert str(domain_err) == "[domain:DOMAIN_X] domain 失败", "__str__ format must stay unchanged"
    assert str(ui_err) == "[ui:UI_X] ui 失败", "__str__ format must stay unchanged"
    assert str(app_err) == "[app:APP_X] app 失败 (d2)", "__str__ format must stay unchanged"
