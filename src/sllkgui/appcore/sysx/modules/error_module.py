from dataclasses import dataclass


@dataclass
class AppError(Exception):
    code: str
    message: str
    layer: str
    details: str = ""

    def __post_init__(self) -> None:
        # FIX-08: dataclass 生成的 __init__ 不会调用 Exception.__init__，
        # 这里补上让 args 非空；__str__ 仍走下方自定义实现，输出格式完全不变。
        super().__init__(self.message)

    def __str__(self) -> str:
        detail = f" ({self.details})" if self.details else ""
        return f"[{self.layer}:{self.code}] {self.message}{detail}"


class IOErrorBoundary(AppError):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(code=code, message=message, layer="io", details=details)


class DomainErrorBoundary(AppError):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(code=code, message=message, layer="domain", details=details)


class UIErrorBoundary(AppError):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(code=code, message=message, layer="ui", details=details)


def to_user_message(error: Exception) -> str:
    if isinstance(error, AppError):
        return f"{error.message} ({error.code})"
    return f"未知错误: {error}"
