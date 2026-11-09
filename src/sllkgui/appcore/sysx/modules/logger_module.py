"""日志系统（标准库 logging 封装）。

- 全局入口：模块级单例 ``Logger``；
- 同时输出控制台（可选彩色，由 console.yaml 的 ``logger_color`` 控制）
  与 ``logs/sllkgui.log``（1MB × 5 滚动文件）；
- 级别由 console.yaml 的 ``logger_level`` 控制（默认 info，调试时按需改 debug）；
- 引导期直接读取 console.yaml，独立于配置框架，避免循环依赖。
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from ..config.paths import data_root, find_resource

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
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
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
    DEFAULT_LOG_FILE_NAME = "sllkgui.log"
    DEFAULT_LOG_MAX_BYTES = 1_048_576
    DEFAULT_LOG_BACKUP_COUNT = 5

    def __init__(self):
        self._logger = logging.getLogger("SllkGUI")
        self._logger.propagate = False
        self._configured = False
        # FIX-05: 导入期不做 I/O；日志目录与滚动文件在首次公开方法调用时才创建，
        # 避免模块导入即按当前工作目录建目录。

    def _ensure_configured(self):
        """惰性入口：首次使用日志时才执行完整配置（含 ``logs/`` 目录创建）。"""
        if not self._configured:
            self._configure_logging()

    def set_level(self, level: str):
        self._ensure_configured()
        level_name = (level or "info").lower()
        target_level = self.LEVELS.get(level_name, logging.INFO)
        self._logger.setLevel(target_level)
        for handler in self._logger.handlers:
            handler.setLevel(target_level)

    def _configure_logging(self):
        if self._configured:
            return
        # FIX-05: 提前置位，避免末尾调用公开 set_level 时其开头的
        # _ensure_configured() 再次递归触发本方法。
        self._configured = True

        if just_fix_windows_console:
            just_fix_windows_console()

        log_dir = data_root() / "logs"

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        color_formatter = _ColorFormatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        use_color = self._read_color_enabled_from_console_config()
        log_file_name, log_max_bytes, log_backup_count = (
            self._read_file_policy_from_console_config()
        )

        if not self._logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(color_formatter if use_color else formatter)

            # 数据目录可能不可写（例如 ``SLLKGUI_DATA_DIR`` 指向一个文件或
            # 只读盘）：日志系统是启动期最先初始化的模块，这里必须降级为
            # 「仅控制台」，而不是把 OSError 抛给启动流程。
            file_handler = None
            failure = None
            try:
                os.makedirs(log_dir, exist_ok=True)
                file_handler = RotatingFileHandler(
                    log_dir / log_file_name,
                    maxBytes=log_max_bytes,
                    backupCount=log_backup_count,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
            except OSError as exc:
                failure = exc

            self._logger.addHandler(console_handler)
            if file_handler is not None:
                self._logger.addHandler(file_handler)
            else:
                self._logger.warning(f"日志目录不可写，已回退为仅控制台输出: {log_dir} ({failure})")

        self.set_level(self._read_level_from_console_config())

    @staticmethod
    def _read_console_config() -> dict:
        """读取 console.yaml（logger 引导期专用，独立于配置框架以避免循环依赖）。"""
        config_path = find_resource("resource/sllkgui/settings/console.yaml")
        if yaml is None or config_path is None or not config_path.exists():
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
            return "info"
        return level.strip().lower()

    @classmethod
    def _read_color_enabled_from_console_config(cls) -> bool:
        enabled = cls._read_console_config().get("logger_color", True)
        if isinstance(enabled, str):
            return enabled.strip().lower() in ("true", "1", "yes", "on")
        return bool(enabled)

    @classmethod
    def _read_file_policy_from_console_config(cls) -> tuple:
        """解析 console.yaml 的 ``logger_file`` 分组，返回 (name, max_bytes, backup_count)。

        配置缺失或类型非法时回落到原默认值，保持原有日志行为。
        """
        section = cls._read_console_config().get("logger_file")
        if not isinstance(section, dict):
            section = {}

        name = section.get("name")
        if not isinstance(name, str) or not name.strip():
            name = cls.DEFAULT_LOG_FILE_NAME
        else:
            name = name.strip()

        max_bytes = section.get("max_bytes")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            max_bytes = cls.DEFAULT_LOG_MAX_BYTES

        backup_count = section.get("backup_count")
        if (
            isinstance(backup_count, bool)
            or not isinstance(backup_count, int)
            or backup_count <= 0
        ):
            backup_count = cls.DEFAULT_LOG_BACKUP_COUNT

        return name, max_bytes, backup_count

    def info(self, msg: str):
        self._ensure_configured()
        self._logger.info(msg)

    def debug(self, msg: str):
        self._ensure_configured()
        self._logger.debug(msg)

    def warning(self, msg: str):
        self._ensure_configured()
        self._logger.warning(msg)

    def error(self, msg: str):
        self._ensure_configured()
        self._logger.error(msg)

    def critical(self, msg: str):
        self._ensure_configured()
        self._logger.critical(msg)

    def exception(self, msg: str):
        """记录错误信息并附带当前异常堆栈（请在 except 块内调用）。"""
        self._ensure_configured()
        self._logger.exception(msg)

    def tool(self, msg: str):
        self._ensure_configured()
        self._logger.info(f"[TOOL] ====={msg}=====")


# 全局logger实例，直接导入Logger即可用
Logger = _Logger()

__all__ = ["Logger"]
