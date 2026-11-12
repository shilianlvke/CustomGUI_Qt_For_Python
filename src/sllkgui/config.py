"""全局配置 API：把路径约定收拢成一个显式入口。

用法::

    import sllkgui
    sllkgui.configure(data_dir="./data", gallery_dir="./data/gallery")
    from sllkgui.appcore import get_app_context      # 顺序不再重要

优先级：**显式参数 > ``SLLKGUI_*`` 环境变量 > 内置默认值**。

``gallery_dir`` 是插件安装根目录；旧的 ``SLLKGUI_APPS_DIR`` 已随 App 协议
一起删除，不再生效。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

__all__ = ["AppConfig", "configure", "current_config", "reset_config", "ConfigAlreadyLoadedError"]


class ConfigAlreadyLoadedError(RuntimeError):
    """配置上下文已经加载后再调用 ``configure()``。

    与其静默失效（旧环境变量的老毛病），这里直接报错，让调用方立刻发现问题。
    确需重建请传 ``force_reload=True``。
    """


@dataclass(frozen=True, slots=True)
class AppConfig:
    """基座的运行期配置。所有字段为 ``None`` 时回落到环境变量/默认值。"""

    gallery_dir: Path | None = None
    resource_dirs: tuple[Path, ...] = ()
    data_dir: Path | None = None
    diagnostics_dir: Path | None = None
    builtin_menus: bool | None = None
    env_fallback: bool = True

    def resolved_gallery_dir(self) -> Path | None:
        if self.gallery_dir is not None:
            return self.gallery_dir
        if self.env_fallback:
            value = _env_path("SLLKGUI_GALLERY_DIR")
            if value is not None:
                return value
        return None

    def resolved_resource_dirs(self) -> tuple[Path, ...]:
        roots = list(self.resource_dirs)
        if self.env_fallback:
            for name in ("SLLKGUI_RESOURCE_DIR", "SLLKGUI_ROOT_DIR"):
                value = _env_path(name)
                if value is not None and value not in roots:
                    roots.append(value)
        return tuple(roots)

    def resolved_data_dir(self) -> Path | None:
        if self.data_dir is not None:
            return self.data_dir
        if self.env_fallback:
            value = _env_path("SLLKGUI_DATA_DIR")
            if value is not None:
                return value
        # 未显式配置时返回 None，由 paths.data_root() 落到程序运行根目录；
        # 不再默认写入 %APPDATA% / ~ 等用户系统目录。
        return None

    def resolved_diagnostics_dir(self) -> Path:
        if self.diagnostics_dir is not None:
            return self.diagnostics_dir
        if self.env_fallback:
            value = _env_path("SLLKGUI_DIAGNOSTICS_DIR")
            if value is not None:
                return value
        data_dir = self.resolved_data_dir()
        if data_dir is None:
            # 延迟导入避免 sllkgui.config 与 appcore.paths 的循环依赖
            from .appcore.sysx.config.paths import program_root

            data_dir = program_root()
        return data_dir / "logs" / "diagnostics"

    def resolved_builtin_menus(self) -> bool:
        if self.builtin_menus is not None:
            return self.builtin_menus
        if self.env_fallback:
            raw = os.getenv("SLLKGUI_BUILTIN_MENUS", "").strip().lower()
            if raw:
                return raw not in {"0", "false", "no", "off"}
        return True


def _env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def _as_path(value: str | os.PathLike[str] | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def _as_paths(values) -> tuple[Path, ...]:
    """批量解析路径并丢弃 ``None``，保证返回类型是纯 ``tuple[Path, ...]``。"""
    return tuple(path for path in (_as_path(value) for value in values) if path is not None)


_ACTIVE: AppConfig = AppConfig()
_CONFIGURED = False


def current_config() -> AppConfig:
    """返回当前生效的配置（未调用 ``configure()`` 时为全默认值 + 环境变量回落）。"""
    return _ACTIVE


def configure(
    *,
    gallery_dir: str | os.PathLike[str] | None = None,
    resource_dirs: tuple[str | os.PathLike[str], ...] | list[str | os.PathLike[str]] | None = None,
    data_dir: str | os.PathLike[str] | None = None,
    diagnostics_dir: str | os.PathLike[str] | None = None,
    builtin_menus: bool | None = None,
    env_fallback: bool | None = None,
    force_reload: bool = False,
) -> AppConfig:
    """设置全局配置并返回生效值。

    ``gallery_dir`` / ``data_dir`` / ``diagnostics_dir`` / ``builtin_menus`` 传
    ``None`` 时保留上次调用的值（首次为 ``None``，由环境变量或默认值回落）；
    ``resource_dirs`` 传 ``None`` 保留、传空序列清空覆盖层；``env_fallback``
    传 ``None`` 保留上次值（打开时以 ``SLLKGUI_*`` 环境变量兜底）。
    """
    global _ACTIVE, _CONFIGURED

    if not force_reload:
        # 上下文已加载时普通 configure() 不会生效，直接报错避免"设了但没起作用"。
        from .appcore.sysx.config import registry as _registry

        if _registry.is_context_loaded():
            raise ConfigAlreadyLoadedError(
                "配置上下文已加载，configure() 不会生效；请在 get_app_context() 之前调用，"
                "或传 force_reload=True 重新加载。"
            )

    _ACTIVE = replace(
        _ACTIVE,
        gallery_dir=_as_path(gallery_dir) or _ACTIVE.gallery_dir,
        resource_dirs=_as_paths(resource_dirs) if resource_dirs is not None else _ACTIVE.resource_dirs,
        data_dir=_as_path(data_dir) or _ACTIVE.data_dir,
        diagnostics_dir=_as_path(diagnostics_dir) or _ACTIVE.diagnostics_dir,
        builtin_menus=_ACTIVE.builtin_menus if builtin_menus is None else builtin_menus,
        env_fallback=_ACTIVE.env_fallback if env_fallback is None else env_fallback,
    )
    _CONFIGURED = True

    if force_reload:
        from .appcore.sysx.config import registry as _registry

        _registry.reset_context()
        # 只有真正重建配置（资源根可能变化）时才让语言缓存失效；
        # 普通 configure() 不动缓存，避免无谓的重扫与测试间相互干扰。
        try:
            from .appcore.sysx.modules.language_module import LANGUAGE_OPTIONS

            LANGUAGE_OPTIONS.invalidate()
        except Exception as exc:
            _log_configure_event(f"语言缓存失效失败（继续使用旧缓存）: {exc}")
        # data_dir 可能已切换：丢弃用户配置缓存，下次读取按新目录解析
        try:
            from .appcore.user_settings import reset_user_settings_cache

            reset_user_settings_cache()
        except Exception as exc:
            _log_configure_event(f"用户配置缓存失效失败（继续使用旧缓存）: {exc}")

    _log_effective_config(_ACTIVE)
    return _ACTIVE


def _log_configure_event(message: str, level: str = "warning") -> None:
    """配置层日志：Logger 尚未就绪时静默，不让日志失败影响配置。"""
    try:
        from .appcore.sysx.modules.logger_module import Logger

        getattr(Logger, level)(message)
    except Exception:
        pass


def _log_effective_config(config: AppConfig) -> None:
    """启动时打印实际生效的目录，便于排查环境变量/显式参数的覆盖关系。"""
    resources = ", ".join(str(path) for path in config.resolved_resource_dirs()) or "-"
    _log_configure_event(
        "配置生效："
        f"gallery={config.resolved_gallery_dir() or '-'} "
        f"data={config.resolved_data_dir() or '-'} "
        f"diagnostics={config.resolved_diagnostics_dir()} "
        f"resources=[{resources}] "
        f"builtin_menus={config.resolved_builtin_menus()} "
        f"env_fallback={config.env_fallback}",
        "info",
    )


def reset_config() -> None:
    """复原为"未配置"状态（测试用）。"""
    global _ACTIVE, _CONFIGURED
    _ACTIVE = AppConfig()
    _CONFIGURED = False
