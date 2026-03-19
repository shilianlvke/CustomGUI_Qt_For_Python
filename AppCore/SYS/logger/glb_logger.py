import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from colorama import just_fix_windows_console
except Exception:
    just_fix_windows_console = None


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
    def _read_level_from_console_config() -> str:
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

    def info(self, msg: str):
        self._logger.info(msg)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def warning(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def tool(self, msg: str):
        self._logger.info(f"[TOOL] ====={msg}=====")


# 全局logger实例，直接导入logger.Logger即可用
Logger = _Logger()
