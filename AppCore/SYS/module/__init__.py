"""Package initialization module."""

# ruff: noqa: N999

from .error_module import (
    AppError as AppError,
)
from .error_module import (
    DomainErrorBoundary as DomainErrorBoundary,
)
from .error_module import (
    IOErrorBoundary as IOErrorBoundary,
)
from .error_module import (
    UIErrorBoundary as UIErrorBoundary,
)
from .error_module import (
    to_user_message as to_user_message,
)
from .plugin_module import (
    CommandPlugin as CommandPlugin,
)
from .plugin_module import (
    MenuPlugin as MenuPlugin,
)
from .plugin_module import (
    PagePlugin as PagePlugin,
)
from .plugin_module import (
    PluginRegistry as PluginRegistry,
)
from .plugin_module import (
    get_plugin_registry as get_plugin_registry,
)
from .telemetry_module import (
    read_recent_events as read_recent_events,
)
from .telemetry_module import (
    record_event as record_event,
)
from .telemetry_module import (
    track_timing as track_timing,
)
from .token_models import ThemeColors as ThemeColors
from .token_models import WindowSettings as WindowSettings
from .token_module import DesignTokens as DesignTokens

__all__ = [
    "AppError",
    "CommandPlugin",
    "DesignTokens",
    "DomainErrorBoundary",
    "IOErrorBoundary",
    "MenuPlugin",
    "PagePlugin",
    "PluginRegistry",
    "ThemeColors",
    "UIErrorBoundary",
    "WindowSettings",
    "get_plugin_registry",
    "read_recent_events",
    "record_event",
    "to_user_message",
    "track_timing",
]
