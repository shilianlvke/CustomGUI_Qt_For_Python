"""插件契约化 KV 存储。

插件只能读写在清单 ``data:`` 中声明的键；值落在 ``ctx.data_dir/<key>.json``，
复用 ``appcore.tool.storage`` 的原子写（RLock + mkstemp + fsync + os.replace +
.bak 回退）。磁盘生命周期与插件数据目录一致：卸载保留，删除插件时随
``GalleryStore.purge`` 一并清除。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sllkgui.appcore import Logger
from sllkgui.appcore.tool.storage import StoreError, read_json, write_json

from .api import GalleryStorage
from .errors import PLUGIN_PATH_ESCAPE, PLUGIN_STORAGE_KEY_UNDECLARED, GalleryError
from .manifest import PluginManifest, ensure_within


class PluginStorage(GalleryStorage):
    """绑定到单个插件的键值视图；键集合由清单声明决定。"""

    def __init__(self, manifest: PluginManifest, data_dir: Path) -> None:
        self._manifest = manifest
        self._data_dir = Path(data_dir)
        self._keys = {item.key for item in manifest.data}

    def _check_declared(self, key: str) -> None:
        if key not in self._keys:
            raise GalleryError(
                PLUGIN_STORAGE_KEY_UNDECLARED,
                f"未声明的存储键: {key}",
                "在 sllkgui-plugin.yml 的 data: 中声明该键",
            )

    def path(self, key: str) -> Path:
        """键对应的 JSON 文件路径（经越界校验）。"""
        self._check_declared(key)
        # key 由 manifest 的 _ID_RE 校验过，这里仍用 ensure_within 兜底
        return ensure_within(self._data_dir, f"{key}.json", code=PLUGIN_PATH_ESCAPE)

    def get(self, key: str, default: Any = None) -> Any:
        """读取键值；未声明的键抛 ``PLUGIN_STORAGE_KEY_UNDECLARED``。"""
        self._check_declared(key)
        try:
            return read_json(self.path(key), default)
        except StoreError as exc:
            Logger.warning(f"[{self._manifest.plugin_id}] 存储读取失败 {key}: {exc}")
            return default

    def set(self, key: str, value: Any) -> bool:
        """原子写键值；成功返回 True，值不可序列化或 IO 失败返回 False。"""
        self._check_declared(key)
        try:
            write_json(self.path(key), value)
            return True
        except (OSError, StoreError, TypeError, ValueError) as exc:
            Logger.warning(f"[{self._manifest.plugin_id}] 存储写入失败 {key}: {exc}")
            return False

    def delete(self, key: str) -> bool:
        """删除键值文件（含 .bak）；不存在视为成功。"""
        self._check_declared(key)
        path = self.path(key)
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".bak").unlink(missing_ok=True)
            return True
        except OSError as exc:
            Logger.warning(f"[{self._manifest.plugin_id}] 存储删除失败 {key}: {exc}")
            return False

    def keys(self) -> tuple[str, ...]:
        """清单声明的全部键（含磁盘上尚未写入的）。"""
        return tuple(sorted(self._keys))


__all__ = ["PluginStorage"]
