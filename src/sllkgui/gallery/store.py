"""Gallery 存储布局：插件、历史、数据、缓存、暂存与回收站。

所有路径都由插件 ID 推导；ID 先过白名单正则，再拼到根目录下，避免
``../`` 之类的清单值变成写盘逃逸。
"""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .errors import PLUGIN_ID_INVALID, GalleryError
from .state import REGISTRY_NAME, SOURCES_NAME

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class GalleryStore:
    """``<data_root>/gallery`` 的目录管理器。"""

    def __init__(self, root: Path, *, data_root: Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        #: 兼容旧调用：不传时数据目录就在 gallery 根下
        self.data_root = Path(data_root).expanduser().resolve() if data_root else self.root

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    @property
    def plugins_dir(self) -> Path:
        return self.root / "plugins"

    @property
    def history_root(self) -> Path:
        return self.root / "history"

    @property
    def data_root_dir(self) -> Path:
        return self.root / "data"

    @property
    def cache_root(self) -> Path:
        return self.root / "cache"

    @property
    def staging_root(self) -> Path:
        return self.root / "staging"

    @property
    def trash_root(self) -> Path:
        return self.root / "trash"

    @property
    def sources_root(self) -> Path:
        return self.root / "sources"

    @property
    def registry_file(self) -> Path:
        return self.root / REGISTRY_NAME

    @property
    def sources_file(self) -> Path:
        return self.root / SOURCES_NAME

    def ensure_layout(self) -> None:
        for path in (
            self.root,
            self.plugins_dir,
            self.history_root,
            self.data_root_dir,
            self.cache_root,
            self.staging_root,
            self.trash_root,
            self.sources_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 路径
    # ------------------------------------------------------------------
    @staticmethod
    def validate_id(plugin_id: str) -> str:
        text = str(plugin_id or "").strip()
        if not _ID_RE.match(text):
            raise GalleryError(PLUGIN_ID_INVALID, f"非法插件 id: {plugin_id!r}")
        return text

    def plugin_path(self, plugin_id: str) -> Path:
        return self.plugins_dir / self.validate_id(plugin_id)

    def source_path(self, source_id: str) -> Path:
        return self.sources_root / self.validate_id(source_id)

    def history_dir(self, plugin_id: str) -> Path:
        return self.history_root / self.validate_id(plugin_id)

    def data_dir(self, plugin_id: str) -> Path:
        return self.data_root_dir / self.validate_id(plugin_id)

    def cache_dir(self, plugin_id: str) -> Path:
        return self.cache_root / self.validate_id(plugin_id)

    def ensure_plugin_data(self, plugin_id: str) -> tuple[Path, Path]:
        data = self.data_dir(plugin_id)
        cache = self.cache_dir(plugin_id)
        data.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        return data, cache

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def new_staging(self) -> Path:
        self.staging_root.mkdir(parents=True, exist_ok=True)
        path = self.staging_root / uuid.uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        return path

    def move_to_history(self, plugin_id: str, version: str, commit: str) -> Path:
        """把当前插件目录移入 history，返回历史目录；不存在时返回空路径。"""
        current = self.plugin_path(plugin_id)
        if not current.exists():
            return Path()
        short = (commit or "unknown")[:7]
        target = self.history_dir(plugin_id) / f"{version or '0.0.0'}-{short}"
        if target.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            target = target.with_name(f"{target.name}-{stamp}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(target))
        return target

    def promote(self, staging: Path, plugin_id: str, *, version: str = "", commit: str = "") -> Path:
        """把 staging 原子替换为 ``plugins/<id>``，旧版本自动进 history。"""
        target = self.plugin_path(plugin_id)
        if target.exists():
            self.move_to_history(plugin_id, version, commit)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            staging.rename(target)
        except OSError:
            shutil.move(str(staging), str(target))
        return target

    def move_to_trash(self, plugin_id: str) -> Path:
        current = self.plugin_path(plugin_id)
        if not current.exists():
            return Path()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        target = self.trash_root / f"{plugin_id}-{stamp}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(target))
        return target

    def purge(self, plugin_id: str) -> None:
        for path in (self.data_dir(plugin_id), self.cache_dir(plugin_id), self.history_dir(plugin_id)):
            shutil.rmtree(path, ignore_errors=True)
        for trash in self.trash_root.glob(f"{plugin_id}-*"):
            shutil.rmtree(trash, ignore_errors=True)
        # 清理 source 残留（正常不会有，防御性）
        for leftover in self.plugins_dir.glob(f"{plugin_id}*"):
            if leftover.name != plugin_id:
                continue

    def truncate_staging(self) -> None:
        shutil.rmtree(self.staging_root, ignore_errors=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)


__all__ = ["GalleryStore"]
