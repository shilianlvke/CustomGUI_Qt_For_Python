"""Gallery 常量：清单名、协议版本、默认源与存储目录名。"""

from __future__ import annotations

from pathlib import Path

MANIFEST_NAME = "sllkgui-plugin.yml"
SOURCE_MANIFEST_NAME = "source.yaml"
ENTRY_MANIFEST_NAME = "entry.yaml"

SUPPORTED_SCHEMA = frozenset({1})
SUPPORTED_API = frozenset({1})
PLUGIN_API_VERSION = 1

GALLERY_DIRNAME = "gallery"
DEFAULT_SOURCE_ID = "official"
DEFAULT_SOURCE_URL = "https://gitee.com/shilianlvke/sllkgui-source.git"
DEFAULT_SOURCE_TRUST = "official"

#: 插件清单最大字节数（防止恶意超大 YAML）
MAX_MANIFEST_BYTES = 256 * 1024
#: 单条遥测事件最大字节数
MAX_EVENT_BYTES = 2 * 1024

#: Git 超时（秒）
GIT_LS_REMOTE_TIMEOUT = 30
GIT_CLONE_TIMEOUT = 120

#: 构建 wheel 后内置插件的相对位置
SHOWCASE_DIRNAME = "showcase"
CORE_PLUGINS_DIRNAME = "core_plugins"


def builtin_root(package_root: Path) -> Path:
    """返回内置插件根（``<package>/showcase`` 与 ``<package>/core_plugins`` 的父级）。"""
    return Path(package_root)


__all__ = [
    "CORE_PLUGINS_DIRNAME",
    "DEFAULT_SOURCE_ID",
    "DEFAULT_SOURCE_TRUST",
    "DEFAULT_SOURCE_URL",
    "ENTRY_MANIFEST_NAME",
    "GALLERY_DIRNAME",
    "GIT_CLONE_TIMEOUT",
    "GIT_LS_REMOTE_TIMEOUT",
    "MANIFEST_NAME",
    "MAX_EVENT_BYTES",
    "MAX_MANIFEST_BYTES",
    "PLUGIN_API_VERSION",
    "SHOWCASE_DIRNAME",
    "SOURCE_MANIFEST_NAME",
    "SUPPORTED_API",
    "SUPPORTED_SCHEMA",
    "builtin_root",
]
