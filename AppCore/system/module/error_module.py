"""模块说明。"""

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    """应用层统一错误对象。

    职责:
    - 表达可结构化处理的错误信息。
    - 统一携带错误码、消息、层级和附加细节。
    """

    code: str
    message: str
    layer: str
    details: str = ""

    def __str__(self) -> str:
        """返回结构化错误字符串表示。"""
        detail = f" ({self.details})" if self.details else ""
        return f"[{self.layer}:{self.code}] {self.message}{detail}"


class IoError(AppError):
    """I/O 层错误边界。"""

    def __init__(self, code: str, message: str, details: str = "") -> None:
        """初始化 I/O 错误对象。

        参数:
        - code: 错误码。
        - message: 面向开发者的错误消息。
        - details: 可选附加信息。
        """
        super().__init__(code=code, message=message, layer="io", details=details)


class DomainError(AppError):
    """领域层错误边界。"""

    def __init__(self, code: str, message: str, details: str = "") -> None:
        """初始化领域错误对象。

        参数:
        - code: 错误码。
        - message: 面向开发者的错误消息。
        - details: 可选附加信息。
        """
        super().__init__(code=code, message=message, layer="domain", details=details)


class UIError(AppError):
    """界面层错误边界。"""

    def __init__(self, code: str, message: str, details: str = "") -> None:
        """初始化界面错误对象。

        参数:
        - code: 错误码。
        - message: 面向开发者的错误消息。
        - details: 可选附加信息。
        """
        super().__init__(code=code, message=message, layer="ui", details=details)


def to_user_message(error: Exception) -> str:
    """将异常转换为可展示给用户的消息。

    参数:
    - error: 任意异常对象。

    返回:
    - str: 用户可读的错误提示文本。
    """
    if isinstance(error, AppError):
        return f"{error.message} ({error.code})"
    return f"未知错误: {error}"


# Backward compatibility aliases.
IOErrorBoundary = IoError
DomainErrorBoundary = DomainError
UIErrorBoundary = UIError
