"""模块说明。"""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

try:
    from colorama import just_fix_windows_console
except ImportError:
    just_fix_windows_console = None


class _ColorFormatter(logging.Formatter):
    """控制台彩色日志格式器。"""

    RESET = "\033[0m"
    LEVEL_COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录并附加颜色。

        参数:
        - record: 日志记录对象。

        返回:
        - str: 格式化后的日志文本。
        """
        message = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno)
        if not color:
            return message
        return f"{color}{message}{self.RESET}"


class _Logger:
    """全局日志门面。

    职责:
    - 统一配置控制台与文件日志输出。
    - 提供简洁的日志调用方法。
    """

    LEVELS: ClassVar[dict[str, int]] = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }

    def __init__(self) -> None:
        """初始化日志门面并完成日志系统配置。"""
        self._logger = logging.getLogger("CustomGUI")
        self._logger.propagate = False
        self._configured = False
        self._configure_logging()

    def set_level(self, level: str) -> None:
        """设置日志级别。

        参数:
        - level: 日志级别文本。

        返回:
        - None
        """
        level_name = (level or "info").lower()
        target_level = self.LEVELS.get(level_name, logging.INFO)
        self._logger.setLevel(target_level)
        for handler in self._logger.handlers:
            handler.setLevel(target_level)

    def _configure_logging(self) -> None:
        """初始化日志处理器与格式器。

        返回:
        - None
        """
        if self._configured:
            return

        if just_fix_windows_console:
            just_fix_windows_console()

        root_dir = Path(__file__).resolve().parents[3]
        log_dir = root_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        color_formatter = _ColorFormatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        use_color = self._read_color_enabled_from_console_config()

        if not self._logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(color_formatter if use_color else formatter)

            file_handler = RotatingFileHandler(
                log_dir / "customgui.log",
                maxBytes=1_048_576,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)

            self._logger.addHandler(console_handler)
            self._logger.addHandler(file_handler)

        self.set_level(self._read_level_from_console_config())
        self._configured = True

    @staticmethod
    def _read_level_from_console_config() -> str:
        """从 console.yml 读取日志级别配置。

        返回:
        - str: 日志级别文本。
        """
        root_dir = Path(__file__).resolve().parents[3]
        config_path = root_dir / "resource" / "CustomUI" / "settings" / "console.yml"
        if not config_path.exists():
            return "debug"

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError:
            return "debug"

        match = re.search(r"^\s*logger_level\s*:\s*([A-Za-z]+)", content, re.MULTILINE)
        if not match:
            return "debug"
        return match.group(1).lower()

    @staticmethod
    def _read_color_enabled_from_console_config() -> bool:
        """从 console.yml 读取彩色日志开关。

        返回:
        - bool: 是否启用彩色控制台输出。
        """
        root_dir = Path(__file__).resolve().parents[3]
        config_path = root_dir / "resource" / "CustomUI" / "settings" / "console.yml"
        if not config_path.exists():
            return True

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError:
            return True

        match = re.search(r"^\s*logger_color\s*:\s*(true|false)\s*$", content, re.MULTILINE | re.IGNORECASE)
        if not match:
            return True
        return match.group(1).lower() == "true"

    def info(self, msg: str) -> None:
        """输出 info 级别日志。"""
        self._logger.info(msg)

    def debug(self, msg: str, *args: object) -> None:
        """输出 debug 级别日志。"""
        self._logger.debug(msg, *args)

    def warning(self, msg: str) -> None:
        """输出 warning 级别日志。"""
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        """输出 error 级别日志。"""
        self._logger.error(msg)

    def tool(self, msg: str) -> None:
        """输出工具阶段标记日志。"""
        self._logger.info("[TOOL] =====%s=====", msg)


# 全局logger实例，直接导入logger.Logger即可用
Logger = _Logger()
