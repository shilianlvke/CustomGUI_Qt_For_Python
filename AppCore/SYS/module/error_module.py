from dataclasses import dataclass


@dataclass
class AppError(Exception):
    code: str
    message: str
    layer: str
    details: str = ""

    def __str__(self):
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
