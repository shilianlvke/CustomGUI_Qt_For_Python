"""日志系统（标准库 logging 封装）。

- 全局入口：模块级单例 ``Logger``；
- 同时输出控制台（可选彩色，由 console.yaml 的 ``logger_color`` 控制）
  与 ``logs/customgui.log``（1MB × 5 滚动文件）；
- 级别由 console.yaml 的 ``logger_level`` 控制（默认 debug）；
- 引导期直接读取 console.yaml，独立于配置框架，避免循环依赖。
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from colorama import just_fix_windows_console
except Exception:
    just_fix_windows_console = None

try:
    import yaml
except Exception:  # PyYAML 缺失时保持 logger 可用
    yaml = None


class _ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",   # Cyan
        logging.INFO: "\033[32m",    # Green
        logging.WARNING: "\033[33m", # Yellow
        logging.ERROR: "\033[31m",   # Red
        logging.CRITICAL: "\033[35m",# Magenta
    }

    def format(self, record):
        message = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno)
        if not color:
            return message
        return f"{color}{message}{self.RESET}"


class _Logger:
    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    def __init__(self):
        self._logger = logging.getLogger("CustomGUI")
        self._logger.propagate = False
        self._configured = False
        self._configure_logging()

    def set_level(self, level: str):
        level_name = (level or "info").lower()
        target_level = self.LEVELS.get(level_name, logging.INFO)
        self._logger.setLevel(target_level)
        for handler in self._logger.handlers:
            handler.setLevel(target_level)

    def _configure_logging(self):
        if self._configured:
            return

        if just_fix_windows_console:
            just_fix_windows_console()

        root_dir = Path(__file__).resolve().parents[3]
        log_dir = root_dir / "logs"
        os.makedirs(log_dir, exist_ok=True)

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
    def _read_console_config() -> dict:
        """读取 console.yaml（logger 引导期专用，独立于配置框架以避免循环依赖）。"""
        config_path = Path(__file__).resolve().parents[3] / "resource" / "CustomUI" / "settings" / "console.yaml"
        if yaml is None or not config_path.exists():
            return {}

        try:
            content = config_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except (OSError, yaml.YAMLError):
            return {}
        return data if isinstance(data, dict) else {}

    @classmethod
    def _read_level_from_console_config(cls) -> str:
        level = cls._read_console_config().get("logger_level")
        if not isinstance(level, str) or not level.strip():
            return "debug"
        return level.strip().lower()

    @classmethod
    def _read_color_enabled_from_console_config(cls) -> bool:
        enabled = cls._read_console_config().get("logger_color", True)
        if isinstance(enabled, str):
            return enabled.strip().lower() in ("true", "1", "yes", "on")
        return bool(enabled)

    def info(self, msg: str):
        self._logger.info(msg)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def warning(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def critical(self, msg: str):
        self._logger.critical(msg)

    def exception(self, msg: str):
        """记录错误信息并附带当前异常堆栈（请在 except 块内调用）。"""
        self._logger.exception(msg)

    def tool(self, msg: str):
        self._logger.info(f"[TOOL] ====={msg}=====")


# 全局logger实例，直接导入Logger即可用
Logger = _Logger()

__all__ = ["Logger"]
