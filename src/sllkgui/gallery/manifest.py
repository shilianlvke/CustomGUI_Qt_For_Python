"""``sllkgui-plugin.yml`` 解析与校验。

清单是插件唯一的运行时契约：加载器、安装器、lint、源仓库校验都从这里读取
同一份数据，避免各处各写一套宽松判断。
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .api import Permission
from .defaults import MANIFEST_NAME, MAX_MANIFEST_BYTES, PLUGIN_API_VERSION, SUPPORTED_API, SUPPORTED_SCHEMA
from .errors import (
    PLUGIN_API_UNSUPPORTED,
    PLUGIN_ENTRY_MISSING,
    PLUGIN_ID_INVALID,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_PATH_ESCAPE,
    PLUGIN_REQUIRES_UNSATISFIED,
    PLUGIN_SCHEMA_UNSUPPORTED,
    PLUGIN_SURFACE_DUPLICATE,
    PLUGIN_SURFACE_EMPTY,
    PLUGIN_VERSION_INVALID,
    GalleryError,
)

__all__ = [
    "DependencySpec",
    "PluginManifest",
    "SurfaceSpec",
    "ensure_within",
    "load_manifest",
    "manifest_sha256",
    "parse_version",
]

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_TITLE_KEYS = ("zh_cn", "zh_tw", "en_us", "ja_jp")


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    title: dict[str, str]
    icon: str = ""
    default: bool = False
    order: int = 100


@dataclass(frozen=True)
class DependencySpec:
    plugin_id: str
    version: str = ""


@dataclass(frozen=True)
class PluginManifest:
    schema: int
    api: int
    plugin_id: str
    name: str
    version: str
    entry: str
    root: Path
    description: str = ""
    license: str = ""
    homepage: str = ""
    repository: str = ""
    requires_sllkgui: str = ""
    requires_python: str = ""
    surfaces: tuple[SurfaceSpec, ...] = ()
    dependencies: tuple[DependencySpec, ...] = ()
    permissions: tuple[Permission, ...] = ()
    manifest_sha256: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def surface(self, surface_id: str) -> SurfaceSpec | None:
        for item in self.surfaces:
            if item.surface_id == surface_id:
                return item
        return None

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME


def parse_version(value: str, *, code: str = PLUGIN_VERSION_INVALID) -> Version:
    try:
        return Version(str(value))
    except InvalidVersion as exc:
        raise GalleryError(code, f"非法版本号: {value!r}", str(exc)) from exc


def ensure_within(root: Path, relative: str | Path, *, code: str = PLUGIN_PATH_ESCAPE) -> Path:
    """把清单里的相对路径解析到 ``root`` 内，拒绝绝对路径与 ``..`` 逃逸。"""
    text = str(relative or "").strip().replace("\\", "/")
    if not text:
        raise GalleryError(code, "路径不能为空")
    candidate = Path(text)
    if candidate.is_absolute() or candidate.drive or text.startswith("//"):
        raise GalleryError(code, f"不允许绝对路径: {text}")
    parts = [part for part in candidate.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise GalleryError(code, f"路径越界: {text}")
    for part in parts:
        stem = part.split(".", 1)[0].lower()
        if stem in _WINDOWS_RESERVED:
            raise GalleryError(code, f"Windows 保留名: {text}")
    resolved = (Path(root).resolve() / Path(*parts)).resolve()
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise GalleryError(code, f"路径越界: {text}", str(exc)) from exc
    return resolved


def manifest_sha256(path: Path) -> str:
    """清单 SHA-256；统一换行后再哈希，保证 Windows/Linux 校验一致。"""
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _read_yaml(path: Path) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise GalleryError(PLUGIN_MANIFEST_INVALID, f"清单不存在: {path}")
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise GalleryError(
            PLUGIN_MANIFEST_INVALID,
            f"清单超过 {MAX_MANIFEST_BYTES} 字节",
            str(path),
        )
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "清单 YAML 解析失败", str(exc)) from exc
    if not isinstance(data, dict):
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "清单顶层必须是映射")
    return data, raw


def _require_str(data: dict[str, Any], key: str, *, code: str = PLUGIN_MANIFEST_INVALID) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GalleryError(code, f"缺少必填字段: {key}")
    return value.strip()


def _parse_title(value: Any, surface_id: str) -> dict[str, str]:
    if isinstance(value, str):
        return {key: value for key in _TITLE_KEYS}
    if not isinstance(value, dict):
        raise GalleryError(PLUGIN_MANIFEST_INVALID, f"Surface {surface_id} 的 title 必须是映射或字符串")
    title: dict[str, str] = {}
    for key, text in value.items():
        if not isinstance(key, str) or not isinstance(text, str):
            continue
        title[key.strip()] = text.strip()
    if not title:
        raise GalleryError(PLUGIN_MANIFEST_INVALID, f"Surface {surface_id} 的 title 为空")
    for key in _TITLE_KEYS:
        title.setdefault(key, title.get("en_us") or next(iter(title.values())))
    return title


def _parse_surfaces(value: Any, root: Path) -> tuple[SurfaceSpec, ...]:
    if not isinstance(value, list) or not value:
        raise GalleryError(PLUGIN_SURFACE_EMPTY, "至少需要声明一个 Surface")
    result: list[SurfaceSpec] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise GalleryError(PLUGIN_MANIFEST_INVALID, f"Surface #{index + 1} 必须是映射")
        surface_id = str(item.get("id") or "").strip()
        if not _ID_RE.match(surface_id):
            raise GalleryError(PLUGIN_ID_INVALID, f"非法 Surface id: {surface_id!r}")
        if surface_id in seen:
            raise GalleryError(PLUGIN_SURFACE_DUPLICATE, f"重复的 Surface id: {surface_id}")
        seen.add(surface_id)
        order = item.get("order", 100)
        if isinstance(order, bool) or not isinstance(order, int):
            order = 100
        icon = str(item.get("icon") or "").strip()
        if icon:
            icon_path = ensure_within(root, icon)
            if not icon_path.is_file():
                icon = ""
        default = bool(item.get("default", False))
        result.append(
            SurfaceSpec(
                surface_id=surface_id,
                title=_parse_title(item.get("title", surface_id), surface_id),
                icon=icon,
                default=default,
                order=order,
            )
        )
    if sum(1 for item in result if item.default) > 1:
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "只能有一个 Surface 标记 default: true")
    return tuple(sorted(result, key=lambda item: (item.order, item.surface_id)))


def _parse_dependencies(value: Any) -> tuple[DependencySpec, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "dependencies 必须是列表")
    result: list[DependencySpec] = []
    for item in value:
        if not isinstance(item, dict):
            raise GalleryError(PLUGIN_MANIFEST_INVALID, "dependencies 条目必须是映射")
        plugin_id = str(item.get("id") or "").strip()
        if not _ID_RE.match(plugin_id):
            raise GalleryError(PLUGIN_ID_INVALID, f"非法依赖 id: {plugin_id!r}")
        version = str(item.get("version") or "").strip()
        if version:
            _validate_specifier(version)
        result.append(DependencySpec(plugin_id=plugin_id, version=version))
    return tuple(result)


def _parse_permissions(value: Any) -> tuple[Permission, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "permissions 必须是列表")
    allowed = {item.value for item in Permission}
    result: list[Permission] = []
    for item in value:
        text = str(item or "").strip()
        if text not in allowed:
            raise GalleryError(PLUGIN_MANIFEST_INVALID, f"未知权限: {text!r}")
        permission = Permission(text)
        if permission not in result:
            result.append(permission)
    return tuple(result)


def _validate_specifier(text: str) -> None:
    try:
        SpecifierSet(text)
    except InvalidSpecifier as exc:
        raise GalleryError(PLUGIN_MANIFEST_INVALID, f"非法版本约束: {text!r}", str(exc)) from exc


def _check_requires(data: dict[str, Any], current_version: str) -> tuple[str, str]:
    requires = data.get("requires") or {}
    if not isinstance(requires, dict):
        raise GalleryError(PLUGIN_MANIFEST_INVALID, "requires 必须是映射")
    sllkgui_spec = str(requires.get("sllkgui") or "").strip()
    python_spec = str(requires.get("python") or "").strip()
    if sllkgui_spec:
        _validate_specifier(sllkgui_spec)
        try:
            compatible = Version(current_version) in SpecifierSet(sllkgui_spec)
        except InvalidVersion:
            compatible = False
        if not compatible:
            raise GalleryError(
                PLUGIN_REQUIRES_UNSATISFIED,
                f"插件要求 sllkgui {sllkgui_spec}，当前 {current_version}",
            )
    if python_spec:
        _validate_specifier(python_spec)
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        if Version(current) not in SpecifierSet(python_spec):
            raise GalleryError(PLUGIN_REQUIRES_UNSATISFIED, f"插件要求 Python {python_spec}，当前 {current}")
    return sllkgui_spec, python_spec


def load_manifest(path: Path, *, current_sllkgui: str | None = None) -> PluginManifest:
    """读取并校验插件清单，返回不可变数据对象。"""
    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / MANIFEST_NAME
    root = manifest_path.parent.resolve()
    data, raw = _read_yaml(manifest_path)

    schema = data.get("schema")
    if schema not in SUPPORTED_SCHEMA:
        raise GalleryError(PLUGIN_SCHEMA_UNSUPPORTED, f"不支持的清单 schema: {schema!r}")
    api = data.get("api")
    if api not in SUPPORTED_API:
        raise GalleryError(PLUGIN_API_UNSUPPORTED, f"不支持的插件 API: {api!r}")

    plugin_id = _require_str(data, "id", code=PLUGIN_ID_INVALID)
    if not _ID_RE.match(plugin_id):
        raise GalleryError(PLUGIN_ID_INVALID, f"非法插件 id: {plugin_id!r}")
    name = _require_str(data, "name")
    version = _require_str(data, "version", code=PLUGIN_VERSION_INVALID)
    parse_version(version)
    entry = str(data.get("entry") or "plugin.py").strip()
    entry_path = ensure_within(root, entry)
    if not entry_path.is_file():
        raise GalleryError(PLUGIN_ENTRY_MISSING, f"入口不存在: {entry}")

    from sllkgui import __version__ as default_version

    requires_sllkgui, requires_python = _check_requires(data, current_sllkgui or default_version)
    surfaces = _parse_surfaces(data.get("surfaces"), root)

    warnings: list[str] = []
    if api != PLUGIN_API_VERSION:
        warnings.append(f"api {api} 与当前实现 {PLUGIN_API_VERSION} 不一致")

    return PluginManifest(
        schema=int(schema),
        api=int(api),
        plugin_id=plugin_id,
        name=name,
        version=version,
        entry=entry,
        root=root,
        description=str(data.get("description") or "").strip(),
        license=str(data.get("license") or "").strip(),
        homepage=str(data.get("homepage") or "").strip(),
        repository=str(data.get("repository") or "").strip(),
        requires_sllkgui=requires_sllkgui,
        requires_python=requires_python,
        surfaces=surfaces,
        dependencies=_parse_dependencies(data.get("dependencies")),
        permissions=_parse_permissions(data.get("permissions")),
        manifest_sha256=hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        warnings=tuple(warnings),
    )
