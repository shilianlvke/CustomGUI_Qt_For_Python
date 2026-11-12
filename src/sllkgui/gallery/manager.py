"""插件安装、更新、回滚、卸载与校验。

所有写操作都通过 :class:`GalleryStore`，状态变化立即落盘 ``registry.json``；
失败路径必须保留旧版本（先 clone/校验到 staging，最后一步才替换目录）。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sllkgui.appcore import Logger, record_event

from . import git_backend
from .errors import (
    PLUGIN_ALREADY_INSTALLED,
    PLUGIN_COMMIT_MISMATCH,
    PLUGIN_DEPENDENCY_DISABLED,
    PLUGIN_HASH_MISMATCH,
    PLUGIN_ID_INVALID,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_NOT_INSTALLED,
    PLUGIN_REMOVE_REQUIRED_BY,
    PLUGIN_SOURCE_CONFLICT,
    PLUGIN_VERSION_NOT_FOUND,
    GalleryError,
)
from .manifest import PluginManifest, load_manifest, manifest_sha256
from .resolver import Candidate, resolve
from .source import PluginEntry, SourceIndex, SourceManager, VersionEntry
from .state import InstalledPlugin, RegistryState, save_registry
from .store import GalleryStore


def _satisfy(installed: str, constraint: str) -> bool:
    from .resolver import _satisfies

    return _satisfies(installed, constraint)


def _commit_matches(expected: str, actual: str) -> bool:
    expected = expected.lower().strip()
    actual = actual.lower().strip()
    if not expected or not actual:
        return False
    return actual.startswith(expected) if len(expected) < 40 else actual == expected


class PluginManager:
    def __init__(
        self,
        store: GalleryStore,
        state: RegistryState,
        sources: SourceManager,
        *,
        base_version: str = "",
    ) -> None:
        self.store = store
        self.state = state
        self.sources = sources
        if base_version:
            self.state.base_version = base_version

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def save(self) -> None:
        save_registry(self.store.registry_file, self.state)

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.store.root).as_posix()
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def installed_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for record in self.state.plugins.values():
            rows.append(
                {
                    "id": record.plugin_id,
                    "version": record.version,
                    "source": record.source_id,
                    "repository": record.repository,
                    "commit": record.commit,
                    "permissions": list(record.permissions),
                    "compliance": record.compliance,
                    "enabled": record.enabled,
                    "path": record.path,
                    "previous": dict(record.previous or {}),
                }
            )
        return rows

    def search(self, query: str = "", *, source_id: str = "") -> list[dict[str, Any]]:
        index = self.sources.index()
        rows: list[dict[str, Any]] = []
        needle = (query or "").strip().lower()
        for plugin_id, entries in sorted(index.entries.items()):
            for entry in entries:
                if source_id and entry.source_id != source_id:
                    continue
                latest = entry.latest()
                if latest is None:
                    continue
                haystack = f"{plugin_id} {entry.name} {entry.summary}".lower()
                if needle and needle not in haystack:
                    continue
                rows.append(
                    {
                        "id": plugin_id,
                        "name": entry.name,
                        "summary": entry.summary,
                        "version": latest.version,
                        "author": entry.author,
                        "categories": list(entry.categories),
                        "source": entry.source_id,
                        "permissions": list(latest.permissions),
                        "compliance": entry.compliance,
                        "repository": entry.repository,
                    }
                )
        return rows

    def info(self, plugin_id: str) -> dict[str, Any]:
        index = self.sources.index()
        entries = index.find(plugin_id)
        installed = self.state.plugins.get(plugin_id)
        if not entries and installed is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"未找到插件: {plugin_id}")
        return {
            "id": plugin_id,
            "installed": None
            if installed is None
            else {
                "version": installed.version,
                "source": installed.source_id,
                "commit": installed.commit,
                "enabled": installed.enabled,
                "permissions": list(installed.permissions),
                "compliance": installed.compliance,
            },
            "sources": [
                {
                    "source": entry.source_id,
                    "name": entry.name,
                    "summary": entry.summary,
                    "author": entry.author,
                    "license": entry.license,
                    "repository": entry.repository,
                    "versions": [
                        {
                            "version": item.version,
                            "ref": item.ref,
                            "commit": item.commit,
                            "yanked": item.yanked,
                            "permissions": list(item.permissions),
                        }
                        for item in entry.versions
                    ],
                }
                for entry in entries
            ],
        }

    # ------------------------------------------------------------------
    # 安装
    # ------------------------------------------------------------------
    def install(
        self,
        plugin_id: str = "",
        *,
        version: str = "",
        source_id: str = "",
        url: str = "",
        ref: str = "",
        allow_local: bool = False,
    ) -> dict[str, Any]:
        if url:
            return self._install_direct(url, ref=ref, allow_local=allow_local)
        if not plugin_id:
            raise GalleryError(PLUGIN_ID_INVALID, "必须提供插件 id 或 --url")
        existing = self.state.plugins.get(plugin_id)
        index = self.sources.index()
        entries = self._select_entries(index, plugin_id, source_id)
        entry = entries[0]
        version_entry = self._select_version(entry, version)
        if (
            existing is not None
            and existing.version == version_entry.version
            and existing.commit
            and _commit_matches(version_entry.commit, existing.commit)
        ):
            raise GalleryError(PLUGIN_ALREADY_INSTALLED, f"插件已安装: {plugin_id} {version_entry.version}")

        candidates = index.candidates()
        root_candidate = Candidate(
            plugin_id=plugin_id,
            version=version_entry.version,
            source_id=entry.source_id,
            dependencies=version_entry.dependencies,
            payload={"entry": entry, "version": version_entry},
        )
        # 根插件始终参与安装；依赖可复用已安装版本
        installed_versions = {
            key: value.version for key, value in self.state.plugins.items() if key != plugin_id
        }
        ordered = resolve(
            {plugin_id: f"=={version_entry.version}"},
            {**candidates, plugin_id: [root_candidate]},
            installed_versions,
        )
        if not ordered:
            raise GalleryError(PLUGIN_ALREADY_INSTALLED, f"插件已安装: {plugin_id}")
        for candidate in ordered:
            self._install_candidate(candidate)
        self.save()
        record_event(
            "plugin.installed",
            category="plugin",
            payload={"id": plugin_id, "version": version_entry.version, "source": entry.source_id},
        )
        Logger.info(f"插件安装完成: {plugin_id} {version_entry.version}")
        return {
            "id": plugin_id,
            "version": version_entry.version,
            "commit": version_entry.commit,
            "source": entry.source_id,
            "dependencies": [item.plugin_id for item in ordered if item.plugin_id != plugin_id],
        }

    def _install_direct(self, url: str, *, ref: str = "", allow_local: bool = False) -> dict[str, Any]:
        staging = self.store.new_staging()
        try:
            commit = git_backend.clone(url, staging, ref=ref or "HEAD", allow_local=allow_local)
            manifest = load_manifest(staging)
            existing = self.state.plugins.get(manifest.plugin_id)
            if existing is not None and existing.version == manifest.version and existing.commit == commit:
                raise GalleryError(
                    PLUGIN_ALREADY_INSTALLED,
                    f"插件已安装: {manifest.plugin_id} {manifest.version}",
                )
            version_entry = VersionEntry(
                version=manifest.version,
                ref=ref or "HEAD",
                commit=commit,
                manifest_sha256=manifest.manifest_sha256,
                api=manifest.api,
                sllkgui=manifest.requires_sllkgui,
                python=manifest.requires_python,
                permissions=tuple(item.value for item in manifest.permissions),
                dependencies=manifest.dependencies,
            )
            entry = PluginEntry(
                plugin_id=manifest.plugin_id,
                name=manifest.name,
                summary=manifest.description,
                author="",
                license=manifest.license,
                repository=url,
                source_id="direct",
                versions=(version_entry,),
                description=manifest.description,
                homepage=manifest.homepage,
                compliance=1,
                path=staging,
            )
            candidate = Candidate(
                plugin_id=manifest.plugin_id,
                version=manifest.version,
                source_id="direct",
                dependencies=manifest.dependencies,
                payload={"entry": entry, "version": version_entry},
            )
            self._install_candidate(candidate, staging=staging)
            self.save()
            record_event(
                "plugin.installed",
                category="plugin",
                payload={"id": manifest.plugin_id, "version": manifest.version, "source": "direct"},
            )
            return {
                "id": manifest.plugin_id,
                "version": manifest.version,
                "commit": commit,
                "source": "direct",
                "dependencies": [],
            }
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _select_entries(self, index: SourceIndex, plugin_id: str, source_id: str) -> list[PluginEntry]:
        entries = index.find(plugin_id)
        if not entries:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"源中没有插件: {plugin_id}")
        if source_id:
            matched = [item for item in entries if item.source_id == source_id]
            if not matched:
                raise GalleryError(PLUGIN_NOT_INSTALLED, f"源 {source_id} 中没有插件: {plugin_id}")
            return matched
        if len(entries) > 1:
            sources = ", ".join(item.source_id for item in entries)
            raise GalleryError(
                PLUGIN_SOURCE_CONFLICT,
                f"插件出现在多个源，请用 --source 指定（{sources}）",
                params={"id": plugin_id, "sources": sources},
            )
        return entries

    def _select_version(self, entry: PluginEntry, version: str) -> VersionEntry:
        if version:
            matched = entry.version(version)
            if matched is None:
                raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"{entry.plugin_id} 没有版本 {version}")
            return matched
        latest = entry.latest()
        if latest is None:
            raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"{entry.plugin_id} 没有可用版本")
        return latest

    def _install_candidate(self, candidate: Candidate, *, staging: Path | None = None) -> None:
        entry: PluginEntry = candidate.payload.get("entry")
        version: VersionEntry = candidate.payload.get("version")
        if entry is None or version is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"缺少安装元数据: {candidate.plugin_id}")

        temporary = staging is not None
        workdir = staging if staging is not None else self.store.new_staging()
        try:
            if staging is None:
                commit = git_backend.clone(
                    entry.repository,
                    workdir,
                    ref=version.ref,
                    allow_local=self.sources.allow_local,
                )
            else:
                commit = git_backend.head(workdir)
            if not _commit_matches(version.commit, commit):
                raise GalleryError(
                    PLUGIN_COMMIT_MISMATCH,
                    f"{entry.plugin_id} 的 commit 与源条目不一致",
                    f"expected={version.commit} actual={commit}",
                )
            manifest = load_manifest(workdir)
            if manifest.plugin_id != entry.plugin_id:
                raise GalleryError(
                    PLUGIN_MANIFEST_INVALID,
                    f"清单 id 与源条目不一致: {manifest.plugin_id} != {entry.plugin_id}",
                )
            if manifest.version != version.version:
                raise GalleryError(
                    PLUGIN_MANIFEST_INVALID,
                    f"清单版本与源条目不一致: {manifest.version} != {version.version}",
                )
            actual_hash = manifest_sha256(manifest.manifest_path)
            if actual_hash.lower() != version.manifest_sha256.lower():
                raise GalleryError(
                    PLUGIN_HASH_MISMATCH,
                    f"{entry.plugin_id} 的清单 SHA-256 与源条目不一致",
                    f"expected={version.manifest_sha256} actual={actual_hash}",
                )
            declared = {item.value for item in manifest.permissions}
            if set(version.permissions) and declared != set(version.permissions):
                raise GalleryError(
                    PLUGIN_MANIFEST_INVALID,
                    f"{entry.plugin_id} 的权限声明与源条目不一致",
                )
            self._promote(manifest, entry, version, commit, workdir)
            self._deprecate_dependents_guard(manifest)
        finally:
            if not temporary and workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)

    def _promote(
        self,
        manifest: PluginManifest,
        entry: PluginEntry,
        version: VersionEntry,
        commit: str,
        staging: Path,
    ) -> None:
        old = self.state.plugins.get(manifest.plugin_id)
        history_path = None
        if old is not None and self.store.plugin_path(manifest.plugin_id).exists():
            history_path = self.store.move_to_history(
                manifest.plugin_id,
                old.version,
                old.commit,
            )
        target = self.store.plugin_path(manifest.plugin_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            try:
                staging.rename(target)
            except OSError:
                shutil.move(str(staging), str(target))
        previous = None
        if old is not None and history_path is not None and history_path.exists():
            previous = {
                "version": old.version,
                "commit": old.commit,
                "path": self._rel(history_path),
            }
        record = InstalledPlugin(
            plugin_id=manifest.plugin_id,
            version=manifest.version,
            source_id=entry.source_id,
            repository=entry.repository,
            requested_ref=version.ref,
            commit=commit,
            manifest_sha256=version.manifest_sha256,
            path=self._rel(target),
            permissions=[item.value for item in manifest.permissions],
            compliance=entry.compliance,
            dependencies={item.plugin_id: item.version for item in manifest.dependencies},
            enabled=True if old is None else old.enabled,
            previous=previous,
        )
        self.state.plugins[manifest.plugin_id] = record
        self.store.ensure_plugin_data(manifest.plugin_id)

    def _deprecate_dependents_guard(self, manifest: PluginManifest) -> None:
        """依赖当前插件的已安装插件若被禁用，记录 warning。"""
        for record in self.state.plugins.values():
            requirement = record.dependencies.get(manifest.plugin_id)
            if requirement and not _satisfy(manifest.version, requirement):
                Logger.warning(
                    f"{record.plugin_id} 依赖 {manifest.plugin_id} {requirement}，"
                    f"当前 {manifest.version} 不满足"
                )

    # ------------------------------------------------------------------
    # 更新 / 回滚
    # ------------------------------------------------------------------
    def update(self, plugin_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        current = self.state.plugins.get(plugin_id)
        if current is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"插件未安装: {plugin_id}")
        entries = self.sources.index().find(plugin_id, source_id=current.source_id)
        if not entries:
            raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"源中没有插件: {plugin_id}")
        entry = entries[0]
        latest = entry.latest()
        if latest is None:
            raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"{plugin_id} 没有可用版本")
        if latest.version == current.version and _commit_matches(current.commit, latest.commit):
            return {"id": plugin_id, "updated": False, "version": current.version}
        if dry_run:
            return {
                "id": plugin_id,
                "updated": False,
                "current": current.version,
                "available": latest.version,
            }
        result = self.install(
            plugin_id,
            version=latest.version,
            source_id=current.source_id,
        )
        record_event(
            "plugin.updated",
            category="plugin",
            payload={"id": plugin_id, "from": current.version, "to": latest.version},
        )
        return {"id": plugin_id, "updated": True, **result}

    def update_all(self, *, dry_run: bool = False) -> list[dict[str, Any]]:
        return [self.update(plugin_id, dry_run=dry_run) for plugin_id in list(self.state.plugins)]

    def rollback(self, plugin_id: str) -> dict[str, Any]:
        current = self.state.plugins.get(plugin_id)
        if current is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"插件未安装: {plugin_id}")
        previous = current.previous or {}
        previous_path = self.store.root / str(previous.get("path") or "")
        if not previous_path.is_dir():
            raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"{plugin_id} 没有可回滚的历史版本")
        history_path = self.store.move_to_history(plugin_id, current.version, current.commit)
        target = self.store.plugin_path(plugin_id)
        shutil.move(str(previous_path), str(target))
        current.version = str(previous.get("version") or "")
        current.commit = str(previous.get("commit") or "")
        current.path = self._rel(target)
        current.previous = (
            {
                "version": current.version,
                "commit": current.commit,
                "path": self._rel(history_path),
            }
            if history_path.exists()
            else None
        )
        self.save()
        record_event("plugin.rolled_back", category="plugin", payload={"id": plugin_id})
        return {"id": plugin_id, "version": current.version}

    # ------------------------------------------------------------------
    # 卸载 / 启停
    # ------------------------------------------------------------------
    def remove(self, plugin_id: str, *, force: bool = False, purge: bool = False) -> dict[str, Any]:
        record = self.state.plugins.get(plugin_id)
        if record is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"插件未安装: {plugin_id}")
        dependents = [
            item.plugin_id
            for item in self.state.plugins.values()
            if plugin_id in item.dependencies and item.plugin_id != plugin_id
        ]
        if dependents and not force:
            raise GalleryError(
                PLUGIN_REMOVE_REQUIRED_BY,
                f"{plugin_id} 被其它插件依赖: {', '.join(dependents)}",
                params={"dependents": dependents},
            )
        if dependents and force:
            for dependent in dependents:
                item = self.state.plugins.get(dependent)
                if item is not None:
                    item.enabled = False
            Logger.warning(f"强制卸载 {plugin_id}，已禁用依赖者: {dependents}")
        trash = self.store.move_to_trash(plugin_id)
        self.state.plugins.pop(plugin_id, None)
        if purge:
            self.store.purge(plugin_id)
        self.save()
        record_event(
            "plugin.removed",
            category="plugin",
            payload={"id": plugin_id, "purged": purge, "trash": bool(trash)},
        )
        return {"id": plugin_id, "trash": self._rel(trash) if trash else "", "purged": purge}

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        record = self.state.plugins.get(plugin_id)
        if record is None:
            raise GalleryError(PLUGIN_NOT_INSTALLED, f"插件未安装: {plugin_id}")
        if enabled:
            for dependency, constraint in record.dependencies.items():
                target = self.state.plugins.get(dependency)
                if target is None:
                    raise GalleryError(
                        PLUGIN_DEPENDENCY_DISABLED,
                        f"依赖未安装: {dependency}",
                        params={"dependency": dependency},
                    )
                if not target.enabled:
                    raise GalleryError(
                        PLUGIN_DEPENDENCY_DISABLED,
                        f"依赖已被禁用: {dependency}",
                        params={"dependency": dependency},
                    )
                if constraint and not _satisfy(target.version, constraint):
                    raise GalleryError(
                        PLUGIN_DEPENDENCY_DISABLED,
                        f"依赖版本不满足: {dependency} {constraint}",
                        params={"dependency": dependency},
                    )
        record.enabled = bool(enabled)
        self.save()
        record_event(
            "plugin.enabled" if enabled else "plugin.disabled",
            category="plugin",
            payload={"id": plugin_id},
        )
        return {"id": plugin_id, "enabled": bool(enabled)}

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def verify(self, plugin_id: str = "") -> list[dict[str, Any]]:
        targets = (
            [self.state.plugins[plugin_id]]
            if plugin_id and plugin_id in self.state.plugins
            else list(self.state.plugins.values())
        )
        results: list[dict[str, Any]] = []
        for record in targets:
            path = self.store.plugin_path(record.plugin_id)
            issues: list[str] = []
            if not path.is_dir():
                issues.append("插件目录不存在")
            else:
                try:
                    manifest = load_manifest(path)
                    if manifest.version != record.version:
                        issues.append(f"清单版本 {manifest.version} != 记录 {record.version}")
                    if record.manifest_sha256 and manifest.manifest_sha256 != record.manifest_sha256:
                        issues.append("清单 SHA-256 与安装记录不一致")
                    if (path / ".git").is_dir():
                        head = git_backend.head(path)
                        if record.commit and not _commit_matches(record.commit, head):
                            issues.append("Git HEAD 与安装记录不一致")
                        if not git_backend.is_clean(path):
                            issues.append("插件工作区不干净")
                except GalleryError as exc:
                    issues.append(str(exc))
            results.append({"id": record.plugin_id, "ok": not issues, "issues": issues})
        return results


__all__ = ["PluginManager"]
