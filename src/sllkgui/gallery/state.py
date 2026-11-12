"""``registry.json`` / ``sources.json`` 的模型与原子读写。

两个文件都属于「坏了也不能阻断启动」的状态数据：读取失败时把原文件备份为
``*.broken-<timestamp>``，以空状态继续运行，并记录一条 warning。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sllkgui.appcore import Logger

REGISTRY_NAME = "registry.json"
SOURCES_NAME = "sources.json"
STATE_SCHEMA = 1


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


@dataclass
class InstalledPlugin:
    plugin_id: str
    version: str
    source_id: str = ""
    repository: str = ""
    requested_ref: str = ""
    commit: str = ""
    manifest_sha256: str = ""
    path: str = ""
    permissions: list[str] = field(default_factory=list)
    compliance: int = 1
    dependencies: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    installed_at: str = field(default_factory=_now_iso)
    previous: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstalledPlugin:
        return cls(
            plugin_id=str(data.get("id") or data.get("plugin_id") or ""),
            version=str(data.get("version") or ""),
            source_id=str(data.get("source_id") or ""),
            repository=str(data.get("repository") or ""),
            requested_ref=str(data.get("requested_ref") or ""),
            commit=str(data.get("commit") or ""),
            manifest_sha256=str(data.get("manifest_sha256") or ""),
            path=str(data.get("path") or ""),
            permissions=[str(item) for item in data.get("permissions") or []],
            compliance=int(data.get("compliance") or 1),
            dependencies={str(k): str(v) for k, v in (data.get("dependencies") or {}).items()},
            enabled=bool(data.get("enabled", True)),
            installed_at=str(data.get("installed_at") or _now_iso()),
            previous=data.get("previous") if isinstance(data.get("previous"), dict) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = payload.pop("plugin_id")
        payload["plugin_id"] = payload["id"]
        return payload


@dataclass
class RegistryState:
    schema: int = STATE_SCHEMA
    updated_at: str = field(default_factory=_now_iso)
    base_version: str = ""
    plugins: dict[str, InstalledPlugin] = field(default_factory=dict)

    def enabled_plugins(self) -> list[InstalledPlugin]:
        return [item for item in self.plugins.values() if item.enabled]


@dataclass
class SourceRecord:
    source_id: str
    url: str
    trust: str = "user"
    enabled: bool = True
    last_refresh: str = ""
    commit: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRecord:
        return cls(
            source_id=str(data.get("id") or data.get("source_id") or ""),
            url=str(data.get("url") or ""),
            trust=str(data.get("trust") or "user"),
            enabled=bool(data.get("enabled", True)),
            last_refresh=str(data.get("last_refresh") or ""),
            commit=str(data.get("commit") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "url": self.url,
            "trust": self.trust,
            "enabled": self.enabled,
            "last_refresh": self.last_refresh,
            "commit": self.commit,
        }


@dataclass
class SourcesState:
    schema: int = STATE_SCHEMA
    sources: list[SourceRecord] = field(default_factory=list)

    def get(self, source_id: str) -> SourceRecord | None:
        for item in self.sources:
            if item.source_id == source_id:
                return item
        return None


def _backup_broken(path: Path) -> None:
    try:
        shutil.move(str(path), f"{path}.broken-{_timestamp()}")
    except OSError as exc:
        Logger.warning(f"状态文件损坏且备份失败 {path}: {exc}")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """临时文件 + ``os.replace``；同目录写入保证原子性。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        Logger.warning(f"状态文件读取失败，已备份并重置: {path}: {exc}")
        _backup_broken(path)
        return None
    if not isinstance(data, dict):
        Logger.warning(f"状态文件顶层不是对象，已备份并重置: {path}")
        _backup_broken(path)
        return None
    return data


def load_registry(path: Path, *, base_version: str = "") -> RegistryState:
    data = _read_json(Path(path))
    if data is None:
        return RegistryState(base_version=base_version)
    raw_plugins = data.get("plugins")
    plugins: dict[str, InstalledPlugin] = {}
    if isinstance(raw_plugins, dict):
        for key, value in raw_plugins.items():
            if not isinstance(value, dict):
                continue
            item = InstalledPlugin.from_dict(value)
            if not item.plugin_id:
                item.plugin_id = str(key)
            if item.plugin_id:
                plugins[item.plugin_id] = item
    return RegistryState(
        schema=int(data.get("schema") or STATE_SCHEMA),
        updated_at=str(data.get("updated_at") or _now_iso()),
        base_version=str(data.get("base_version") or base_version),
        plugins=plugins,
    )


def save_registry(path: Path, state: RegistryState) -> None:
    state.updated_at = _now_iso()
    atomic_write_json(
        Path(path),
        {
            "schema": state.schema,
            "updated_at": state.updated_at,
            "base_version": state.base_version,
            "plugins": {key: item.to_dict() for key, item in state.plugins.items()},
        },
    )


def load_sources(path: Path) -> SourcesState:
    data = _read_json(Path(path))
    if data is None:
        return SourcesState()
    raw = data.get("sources")
    sources: list[SourceRecord] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            record = SourceRecord.from_dict(item)
            if record.source_id and record.url:
                sources.append(record)
    return SourcesState(schema=int(data.get("schema") or STATE_SCHEMA), sources=sources)


def save_sources(path: Path, state: SourcesState) -> None:
    atomic_write_json(
        Path(path),
        {"schema": state.schema, "sources": [item.to_dict() for item in state.sources]},
    )


__all__ = [
    "InstalledPlugin",
    "REGISTRY_NAME",
    "RegistryState",
    "SOURCES_NAME",
    "SourceRecord",
    "SourcesState",
    "atomic_write_json",
    "load_registry",
    "load_sources",
    "save_registry",
    "save_sources",
]
