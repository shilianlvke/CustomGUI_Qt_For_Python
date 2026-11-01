"""全局配置 API：把原先散落在 5 个环境变量里的路径约定收拢成一个显式入口。

旧的用法（仍然兼容）::

    os.environ["CUSTOMGUI_APPS_DIR"] = "./apps"
    os.environ["CUSTOMGUI_DATA_DIR"] = "./data"
    from customgui.appcore import get_app_context      # 必须在上面之后

新用法::

    import customgui
    customgui.configure(apps_dir="./apps", data_dir="./data")
    from customgui.appcore import get_app_context      # 顺序不再重要

优先级：**显式参数 > ``CUSTOMGUI_*`` 环境变量 > 内置默认值**。
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

    apps_dir: Path | None = None
    resource_dirs: tuple[Path, ...] = ()
    data_dir: Path | None = None
    diagnostics_dir: Path | None = None
    builtin_menus: bool | None = None
    strict_plugins: bool = False
    env_fallback: bool = True

    def resolved_apps_dir(self) -> Path | None:
        if self.apps_dir is not None:
            return self.apps_dir
        if self.env_fallback:
            value = _env_path("CUSTOMGUI_APPS_DIR")
            if value is not None:
                return value
        return None

    def resolved_resource_dirs(self) -> tuple[Path, ...]:
        roots = list(self.resource_dirs)
        if self.env_fallback:
            for name in ("CUSTOMGUI_RESOURCE_DIR", "CUSTOMGUI_ROOT_DIR"):
                value = _env_path(name)
                if value is not None and value not in roots:
                    roots.append(value)
        return tuple(roots)

    def resolved_data_dir(self) -> Path | None:
        if self.data_dir is not None:
            return self.data_dir
        if self.env_fallback:
            value = _env_path("CUSTOMGUI_DATA_DIR")
            if value is not None:
                return value
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata).expanduser().resolve() / "CustomGUI"
        return Path.home() / ".customgui"

    def resolved_diagnostics_dir(self) -> Path:
        if self.diagnostics_dir is not None:
            return self.diagnostics_dir
        if self.env_fallback:
            value = _env_path("CUSTOMGUI_DIAGNOSTICS_DIR")
            if value is not None:
                return value
        data_dir = self.resolved_data_dir() or Path.home() / ".customgui"
        return data_dir / "logs" / "diagnostics"

    def resolved_builtin_menus(self) -> bool:
        if self.builtin_menus is not None:
            return self.builtin_menus
        if self.env_fallback:
            raw = os.getenv("CUSTOMGUI_BUILTIN_MENUS", "").strip().lower()
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


_ACTIVE: AppConfig = AppConfig()
_CONFIGURED = False


def current_config() -> AppConfig:
    """返回当前生效的配置（未调用 ``configure()`` 时为全默认值 + 环境变量回落）。"""
    return _ACTIVE


def configure(
    *,
    apps_dir: str | os.PathLike[str] | None = None,
    resource_dirs: tuple[str | os.PathLike[str], ...] | list[str | os.PathLike[str]] | None = None,
    data_dir: str | os.PathLike[str] | None = None,
    diagnostics_dir: str | os.PathLike[str] | None = None,
    builtin_menus: bool | None = None,
    strict_plugins: bool | None = None,
    env_fallback: bool = True,
    force_reload: bool = False,
) -> AppConfig:
    """设置全局配置并返回生效值。

    参数为 ``None`` 的字段保持默认（或环境变量兜底），不会被清空。
    """
    global _ACTIVE, _CONFIGURED

    if _CONFIGURED and not force_reload:
        # 已加载过上下文：重载才能生效，避免"设了但没起作用"的静默失败。
        from .appcore.sysx.config import registry as _registry

        if _registry.is_context_loaded():
            raise ConfigAlreadyLoadedError(
                "configure() 在配置上下文已加载后才会生效；请在 get_app_context() 之前调用，"
                "或传 force_reload=True 重新加载。"
            )

    _ACTIVE = replace(
        _ACTIVE,
        apps_dir=_as_path(apps_dir) or _ACTIVE.apps_dir,
        resource_dirs=tuple(_as_path(p) for p in resource_dirs) if resource_dirs else _ACTIVE.resource_dirs,
        data_dir=_as_path(data_dir) or _ACTIVE.data_dir,
        diagnostics_dir=_as_path(diagnostics_dir) or _ACTIVE.diagnostics_dir,
        builtin_menus=_ACTIVE.builtin_menus if builtin_menus is None else builtin_menus,
        strict_plugins=_ACTIVE.strict_plugins if strict_plugins is None else strict_plugins,
        env_fallback=env_fallback,
    )
    _CONFIGURED = True

    if force_reload:
        from .appcore.sysx.config import registry as _registry

        _registry.reset_context()

    return _ACTIVE


def reset_config() -> None:
    """复原为"未配置"状态（测试用）。"""
    global _ACTIVE, _CONFIGURED
    _ACTIVE = AppConfig()
    _CONFIGURED = False
