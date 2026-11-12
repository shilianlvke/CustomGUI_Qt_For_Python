"""Gallery 存储布局：插件、历史、数据、缓存、暂存与回收站。

所有路径都由插件 ID 推导；ID 先过白名单正则，再拼到根目录下，避免
``../`` 之类的清单值变成写盘逃逸。
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sllkgui.appcore import Logger

from .errors import PLUGIN_ID_INVALID, GalleryError
from .state import REGISTRY_NAME, SOURCES_NAME

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
#: 目录改名的重试间隔（秒）：Windows 上杀毒/索引器会短暂占用刚下载的文件
_RENAME_RETRY_DELAYS = (0.0, 0.15, 0.35, 0.75, 1.5)


def _force_remove(func, path, _error) -> None:
    """``rmtree`` 回调：Git 对象是只读文件，先清属性再重试删除。"""
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    func(path)


def _timestamp() -> str:
    """同一秒内多次安装也不重名的归档时间戳。"""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def remove_dir(path: Path) -> None:
    """删除目录；只读文件（Git pack/idx）也能清掉，目录不存在时静默返回。"""
    target = Path(path)
    if not target.exists():
        return
    shutil.rmtree(target, onexc=_force_remove)


def _rename_dir(src: Path, dst: Path) -> None:
    """目录改名；遇到 Windows 上的短暂占用时按间隔重试。"""
    last: OSError | None = None
    for delay in _RENAME_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            Path(src).rename(dst)
            return
        except OSError as exc:
            last = exc
    if last is not None:
        raise last
    raise OSError("目录改名失败")


def move_dir(src: Path, dst: Path) -> None:
    """移动目录：优先改名，失败后退回复制 + 强制删除。

    只用于暂存目录等一次性数据；需要保留原目录完整性时（如旧版本归档）
    调用方应先复制再改名，避免删除失败留下半个目录。
    """
    try:
        _rename_dir(src, dst)
        return
    except OSError:
        Logger.debug(f"目录改名失败，回退复制: {src} -> {dst}")
    try:
        shutil.copytree(src, dst, symlinks=True)
    except OSError:
        try:
            remove_dir(dst)
        except OSError:
            pass
        raise
    remove_dir(src)


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
            target = target.with_name(f"{target.name}-{_timestamp()}")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _rename_dir(current, target)
            return target
        except OSError:
            Logger.debug(f"旧版本目录被占用，改为复制归档: {current} -> {target}")
        # Windows 下旧目录可能仍被占用（杀毒/索引器/运行中的插件），
        # 不能就地 rmtree：先完整复制到 history，再把旧目录移入 trash。
        # 这一步失败就清理副本并中止，保证插件目录仍完整。
        try:
            shutil.copytree(current, target, symlinks=True)
        except OSError:
            try:
                remove_dir(target)
            except OSError:
                pass
            raise
        trash = self.trash_root / f"{plugin_id}-{_timestamp()}"
        trash.parent.mkdir(parents=True, exist_ok=True)
        try:
            _rename_dir(current, trash)
        except OSError:
            try:
                remove_dir(target)
            except OSError:
                pass
            raise
        try:
            remove_dir(trash)
        except OSError as exc:
            Logger.warning(f"旧版本临时目录清理失败: {trash}: {exc}")
        return target

    def place_staging(self, staging: Path, plugin_id: str) -> Path:
        """把暂存目录移入 ``plugins/<id>``；目标必须已被移走。"""
        target = self.plugin_path(plugin_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        move_dir(Path(staging), target)
        return target

    def promote(self, staging: Path, plugin_id: str, *, version: str = "", commit: str = "") -> Path:
        """把 staging 原子替换为 ``plugins/<id>``，旧版本自动进 history。"""
        if self.plugin_path(plugin_id).exists():
            self.move_to_history(plugin_id, version, commit)
        return self.place_staging(staging, plugin_id)

    def move_to_trash(self, plugin_id: str) -> Path:
        current = self.plugin_path(plugin_id)
        if not current.exists():
            return Path()
        stamp = _timestamp()
        target = self.trash_root / f"{plugin_id}-{stamp}"
        target.parent.mkdir(parents=True, exist_ok=True)
        move_dir(current, target)
        return target

    def purge(self, plugin_id: str) -> None:
        for path in (self.data_dir(plugin_id), self.cache_dir(plugin_id), self.history_dir(plugin_id)):
            try:
                remove_dir(path)
            except OSError as exc:
                Logger.warning(f"清理插件目录失败 {path}: {exc}")
        for trash in self.trash_root.glob(f"{plugin_id}-*"):
            try:
                remove_dir(trash)
            except OSError as exc:
                Logger.warning(f"清理插件回收站失败 {trash}: {exc}")
        # 清理 source 残留（正常不会有，防御性）
        for leftover in self.plugins_dir.glob(f"{plugin_id}*"):
            if leftover.name != plugin_id:
                continue

    def truncate_staging(self) -> None:
        try:
            remove_dir(self.staging_root)
        except OSError as exc:
            Logger.warning(f"清理暂存目录失败 {self.staging_root}: {exc}")
        self.staging_root.mkdir(parents=True, exist_ok=True)


__all__ = ["GalleryStore", "move_dir", "remove_dir"]
