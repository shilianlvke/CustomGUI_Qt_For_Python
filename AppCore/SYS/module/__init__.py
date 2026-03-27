"""Package initialization module."""

# ruff: noqa: N999

from .color_module import ColorPalette as ColorPalette
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
from .language_module import Language as Language
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
from .token_module import DesignTokens as DesignTokens
from .token_module import get_design_tokens as get_design_tokens

__all__ = [
    "AppError",
    "ColorPalette",
    "CommandPlugin",
    "DesignTokens",
    "DomainErrorBoundary",
    "IOErrorBoundary",
    "Language",
    "MenuPlugin",
    "PagePlugin",
    "PluginRegistry",
    "UIErrorBoundary",
    "get_design_tokens",
    "get_plugin_registry",
    "read_recent_events",
    "record_event",
    "to_user_message",
    "track_timing",
]

