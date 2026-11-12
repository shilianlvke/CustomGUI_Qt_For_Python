"""源仓库：刷新、索引、信任分级与条目校验。

源仓库只存元信息（``source.yaml`` + ``plugins/<id>/entry.yaml``），插件代码
仍由开发者自己的 Git 仓库提供。刷新用浅 fetch，坏条目跳过并记录 warning，
单个源失败不影响其它源。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from sllkgui.appcore import Logger

from . import git_backend
from .defaults import (
    DEFAULT_SOURCE_ID,
    DEFAULT_SOURCE_TRUST,
    DEFAULT_SOURCE_URL,
    ENTRY_MANIFEST_NAME,
    SOURCE_MANIFEST_NAME,
)
from .errors import (
    PLUGIN_VERSION_INVALID,
    SOURCE_DUPLICATE,
    SOURCE_INVALID,
    SOURCE_NOT_FOUND,
    SOURCE_REFRESH_FAILED,
    GalleryError,
)
from .manifest import DependencySpec
from .resolver import Candidate
from .state import SourceRecord, SourcesState
from .store import GalleryStore

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class VersionEntry:
    version: str
    ref: str
    commit: str
    manifest_sha256: str
    api: int = 1
    sllkgui: str = ""
    python: str = ""
    permissions: tuple[str, ...] = ()
    dependencies: tuple[DependencySpec, ...] = ()
    yanked: bool = False


@dataclass(frozen=True)
class PluginEntry:
    plugin_id: str
    name: str
    summary: str
    author: str
    license: str
    repository: str
    source_id: str
    versions: tuple[VersionEntry, ...]
    description: str = ""
    homepage: str = ""
    categories: tuple[str, ...] = ()
    icon: str = ""
    screenshots: tuple[str, ...] = ()
    compliance: int = 1
    path: Path | None = None

    def latest(self, *, allow_yanked: bool = False) -> VersionEntry | None:
        usable = [item for item in self.versions if allow_yanked or not item.yanked]
        stable = [item for item in usable if not _is_prerelease(item.version)]
        pool = stable or usable
        if not pool:
            return None
        return max(pool, key=lambda item: Version(item.version))

    def version(self, value: str) -> VersionEntry | None:
        for item in self.versions:
            if item.version == value:
                return item
        return None


@dataclass
class SourceInfo:
    source_id: str
    name: str
    description: str = ""
    maintainers: tuple[str, ...] = ()
    homepage: str = ""
    updated_at: str = ""
    path: Path | None = None


@dataclass
class SourceIndex:
    sources: list[SourceInfo] = field(default_factory=list)
    entries: dict[str, list[PluginEntry]] = field(default_factory=dict)

    def candidates(self) -> dict[str, list[Candidate]]:
        result: dict[str, list[Candidate]] = {}
        for plugin_id, entries in self.entries.items():
            for entry in entries:
                for version in entry.versions:
                    result.setdefault(plugin_id, []).append(
                        Candidate(
                            plugin_id=plugin_id,
                            version=version.version,
                            source_id=entry.source_id,
                            dependencies=version.dependencies,
                            yanked=version.yanked,
                            payload={"entry": entry, "version": version},
                        )
                    )
        return result

    def find(self, plugin_id: str, *, source_id: str = "") -> list[PluginEntry]:
        items = self.entries.get(plugin_id) or []
        if source_id:
            return [item for item in items if item.source_id == source_id]
        return list(items)


def _is_prerelease(value: str) -> bool:
    try:
        return Version(value).is_prerelease
    except InvalidVersion:
        return False


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GalleryError(SOURCE_INVALID, f"源文件不存在: {path.name}", str(path))
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GalleryError(SOURCE_INVALID, f"源 YAML 解析失败: {path.name}", str(exc)) from exc
    if not isinstance(data, dict):
        raise GalleryError(SOURCE_INVALID, f"源 YAML 顶层必须是映射: {path.name}")
    return data


def _text(data: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if required:
        raise GalleryError(SOURCE_INVALID, f"缺少字段: {key}")
    return ""


def _valid_specifier(value: str) -> bool:
    if not value:
        return True
    try:
        SpecifierSet(value)
        return True
    except InvalidSpecifier:
        return False


def _parse_source(path: Path) -> SourceInfo:
    data = _read_yaml(path / SOURCE_MANIFEST_NAME)
    if data.get("schema") != 1:
        raise GalleryError(SOURCE_INVALID, f"不支持的源 schema: {data.get('schema')!r}")
    source_id = _text(data, "id")
    if not _ID_RE.match(source_id):
        raise GalleryError(SOURCE_INVALID, f"非法源 id: {source_id!r}")
    maintainers = data.get("maintainers")
    if not isinstance(maintainers, list) or not maintainers:
        raise GalleryError(SOURCE_INVALID, "source.yaml 缺少 maintainers")
    return SourceInfo(
        source_id=source_id,
        name=_text(data, "name"),
        description=_text(data, "description", required=False),
        maintainers=tuple(str(item).strip() for item in maintainers if str(item).strip()),
        homepage=_text(data, "homepage", required=False),
        updated_at=str(data.get("updated_at") or ""),
        path=path,
    )


def _parse_dependencies(value: Any) -> tuple[DependencySpec, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GalleryError(SOURCE_INVALID, "versions[].dependencies 必须是列表")
    result: list[DependencySpec] = []
    for item in value:
        if not isinstance(item, dict):
            raise GalleryError(SOURCE_INVALID, "依赖条目必须是映射")
        plugin_id = str(item.get("id") or "").strip()
        if not _ID_RE.match(plugin_id):
            raise GalleryError(SOURCE_INVALID, f"非法依赖 id: {plugin_id!r}")
        version = str(item.get("version") or "").strip()
        if version and not _valid_specifier(version):
            raise GalleryError(SOURCE_INVALID, f"非法依赖约束: {version!r}")
        result.append(DependencySpec(plugin_id=plugin_id, version=version))
    return tuple(result)


def _parse_version(item: Any) -> VersionEntry:
    if not isinstance(item, dict):
        raise GalleryError(SOURCE_INVALID, "versions 条目必须是映射")
    version = _text(item, "version")
    try:
        Version(version)
    except InvalidVersion as exc:
        raise GalleryError(PLUGIN_VERSION_INVALID, f"非法版本: {version!r}", str(exc)) from exc
    commit = _text(item, "commit")
    if not _SHA_RE.match(commit):
        raise GalleryError(SOURCE_INVALID, f"非法 commit: {commit!r}")
    sha256 = _text(item, "manifest_sha256")
    if not _SHA256_RE.match(sha256):
        raise GalleryError(SOURCE_INVALID, f"非法 manifest_sha256: {sha256!r}")
    api = item.get("api", 1)
    if api != 1:
        raise GalleryError(SOURCE_INVALID, f"不支持的插件 API: {api!r}")
    sllkgui_spec = str(item.get("sllkgui") or "").strip()
    python_spec = str(item.get("python") or "").strip()
    if not _valid_specifier(sllkgui_spec) or not _valid_specifier(python_spec):
        raise GalleryError(SOURCE_INVALID, f"{version} 的兼容范围非法")
    permissions = item.get("permissions") or []
    if not isinstance(permissions, list):
        raise GalleryError(SOURCE_INVALID, "permissions 必须是列表")
    return VersionEntry(
        version=version,
        ref=str(item.get("ref") or f"v{version}").strip(),
        commit=commit.lower(),
        manifest_sha256=sha256.lower(),
        api=int(api),
        sllkgui=sllkgui_spec,
        python=python_spec,
        permissions=tuple(str(value) for value in permissions),
        dependencies=_parse_dependencies(item.get("dependencies")),
        yanked=bool(item.get("yanked", False)),
    )


def _parse_entry(path: Path, source_id: str) -> PluginEntry:
    data = _read_yaml(path / ENTRY_MANIFEST_NAME)
    if data.get("schema") != 1:
        raise GalleryError(SOURCE_INVALID, f"不支持的 entry schema: {data.get('schema')!r}")
    plugin_id = _text(data, "id")
    if not _ID_RE.match(plugin_id):
        raise GalleryError(SOURCE_INVALID, f"非法插件 id: {plugin_id!r}")
    if path.name != plugin_id:
        raise GalleryError(SOURCE_INVALID, f"目录名与插件 id 不一致: {path.name} != {plugin_id}")
    versions_raw = data.get("versions")
    if not isinstance(versions_raw, list) or not versions_raw:
        raise GalleryError(SOURCE_INVALID, f"{plugin_id} 没有版本记录")
    versions = tuple(_parse_version(item) for item in versions_raw)
    categories = data.get("categories") or []
    if not isinstance(categories, list) or not categories:
        raise GalleryError(SOURCE_INVALID, f"{plugin_id} 缺少 categories")
    screenshots = data.get("screenshots") or []
    if not isinstance(screenshots, list):
        raise GalleryError(SOURCE_INVALID, f"{plugin_id} 的 screenshots 必须是列表")
    compliance = data.get("compliance")
    if compliance != 1:
        raise GalleryError(SOURCE_INVALID, f"{plugin_id} 必须声明 compliance: 1")
    icon = str(data.get("icon") or "").strip()
    if icon and not (path / icon).is_file():
        Logger.warning(f"源条目图标缺失: {plugin_id}/{icon}")
        icon = ""
    return PluginEntry(
        plugin_id=plugin_id,
        name=_text(data, "name"),
        summary=_text(data, "summary"),
        author=_text(data, "author"),
        license=_text(data, "license"),
        repository=_text(data, "repository"),
        source_id=source_id,
        versions=versions,
        description=str(data.get("description") or "").strip(),
        homepage=str(data.get("homepage") or "").strip(),
        categories=tuple(str(item) for item in categories),
        icon=icon,
        screenshots=tuple(str(item) for item in screenshots),
        compliance=int(compliance),
        path=path,
    )


def _parse_categories(root: Path) -> set[str]:
    path = root / "categories.yaml"
    if not path.is_file():
        return set()
    data = _read_yaml(path)
    values = data.get("categories") or []
    if isinstance(values, list):
        return {str(item).strip() for item in values if str(item).strip()}
    return set()


class SourceManager:
    """源配置、刷新与索引聚合。"""

    def __init__(
        self,
        store: GalleryStore,
        state: SourcesState,
        *,
        allow_local: bool = False,
    ) -> None:
        self.store = store
        self.state = state
        self.allow_local = allow_local

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def save(self) -> None:
        from .state import save_sources

        save_sources(self.store.sources_file, self.state)

    def ensure_official(self) -> SourceRecord:
        existing = self.state.get(DEFAULT_SOURCE_ID)
        if existing is not None:
            return existing
        record = SourceRecord(
            source_id=DEFAULT_SOURCE_ID,
            url=DEFAULT_SOURCE_URL,
            trust=DEFAULT_SOURCE_TRUST,
            enabled=True,
        )
        self.state.sources.append(record)
        self.save()
        return record

    def list(self) -> list[SourceRecord]:
        return list(self.state.sources)

    def info(self, source_id: str) -> SourceInfo:
        record = self.state.get(source_id)
        if record is None:
            raise GalleryError(SOURCE_NOT_FOUND, f"源不存在: {source_id}")
        path = self.store.source_path(source_id)
        return _parse_source(path) if (path / SOURCE_MANIFEST_NAME).is_file() else SourceInfo(
            source_id=source_id, name=source_id, path=path
        )

    def add(
        self,
        url: str,
        *,
        source_id: str = "",
        trust: str = "user",
        enabled: bool = True,
        refresh: bool = False,
    ) -> SourceRecord:
        git_backend.validate_url(url, allow_local=self.allow_local)
        record_id = str(source_id or "").strip() or self._derive_id(url)
        if not _ID_RE.match(record_id):
            raise GalleryError(SOURCE_INVALID, f"非法源 id: {record_id!r}")
        if self.state.get(record_id) is not None:
            raise GalleryError(SOURCE_DUPLICATE, f"源已存在: {record_id}")
        record = SourceRecord(
            source_id=record_id,
            url=url,
            trust="official" if trust == "official" else "user",
            enabled=bool(enabled),
        )
        self.state.sources.append(record)
        self.save()
        Logger.info(f"添加源: {record_id} -> {git_backend.redact_url(url)}")
        if refresh:
            self.refresh(record_id)
        return record

    def remove(self, source_id: str) -> None:
        record = self.state.get(source_id)
        if record is None:
            raise GalleryError(SOURCE_NOT_FOUND, f"源不存在: {source_id}")
        self.state.sources = [item for item in self.state.sources if item.source_id != source_id]
        self.save()
        import shutil

        shutil.rmtree(self.store.source_path(source_id), ignore_errors=True)
        Logger.info(f"移除源: {source_id}")

    def set_enabled(self, source_id: str, enabled: bool) -> SourceRecord:
        """启用/停用源：停用后索引与批量刷新都会跳过该源。"""
        record = self.state.get(source_id)
        if record is None:
            raise GalleryError(SOURCE_NOT_FOUND, f"源不存在: {source_id}")
        record.enabled = bool(enabled)
        self.save()
        Logger.info(f"{'启用' if enabled else '停用'}源: {source_id}")
        return record

    def _derive_id(self, url: str) -> str:
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[:-4]
        name = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")
        return name or "source"

    # ------------------------------------------------------------------
    # 刷新与索引
    # ------------------------------------------------------------------
    def refresh(self, source_id: str) -> SourceRecord:
        record = self.state.get(source_id)
        if record is None:
            raise GalleryError(SOURCE_NOT_FOUND, f"源不存在: {source_id}")
        destination = self.store.source_path(source_id)
        try:
            if (destination / ".git").is_dir():
                commit = git_backend.refresh(record.url, destination, allow_local=self.allow_local)
            else:
                commit = git_backend.clone(
                    record.url, destination, allow_local=self.allow_local
                )
            _parse_source(destination)
            for entry_dir in sorted((destination / "plugins").glob("*")):
                if not entry_dir.is_dir():
                    continue
                try:
                    _parse_entry(entry_dir, source_id)
                except GalleryError as exc:
                    Logger.warning(f"源条目无效，已跳过: {source_id}/{entry_dir.name}: {exc}")
        except GalleryError:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一收敛为源刷新失败
            raise GalleryError(
                SOURCE_REFRESH_FAILED,
                f"源刷新失败: {source_id}",
                str(exc),
            ) from exc
        record.commit = commit
        record.last_refresh = datetime.now(UTC).isoformat()
        self.save()
        Logger.info(f"源刷新完成: {source_id} @ {commit[:8]}")
        return record

    def refresh_all(self) -> list[SourceRecord]:
        return [self.refresh(record.source_id) for record in self.list() if record.enabled]

    def index(self) -> SourceIndex:
        """读取所有启用源的索引；坏条目/坏源跳过。"""
        index = SourceIndex()
        for record in self.list():
            if not record.enabled:
                continue
            root = self.store.source_path(record.source_id)
            if not (root / SOURCE_MANIFEST_NAME).is_file():
                Logger.debug(f"源尚未刷新，跳过: {record.source_id}")
                continue
            try:
                info = _parse_source(root)
            except GalleryError as exc:
                Logger.warning(f"源元信息无效，跳过: {record.source_id}: {exc}")
                continue
            index.sources.append(info)
            allowed = _parse_categories(root)
            for entry_dir in sorted((root / "plugins").glob("*")):
                if not entry_dir.is_dir():
                    continue
                try:
                    entry = _parse_entry(entry_dir, record.source_id)
                except GalleryError as exc:
                    Logger.warning(f"源条目无效，已跳过: {record.source_id}/{entry_dir.name}: {exc}")
                    continue
                unknown = [item for item in entry.categories if allowed and item not in allowed]
                if unknown:
                    Logger.warning(f"源条目使用未知分类，已跳过: {entry.plugin_id}: {unknown}")
                    continue
                index.entries.setdefault(entry.plugin_id, []).append(entry)
        return index


__all__ = [
    "PluginEntry",
    "SourceIndex",
    "SourceInfo",
    "SourceManager",
    "VersionEntry",
]
