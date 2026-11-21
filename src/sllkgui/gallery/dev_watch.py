"""开发插件目录文件监听：轮询指纹，防抖后回调变化的插件根目录。

只用于 ``sllkgui run --plugin-dir ... --watch``。不监听已安装插件目录，
不写 registry，不改变版本；失败由窗口层隔离并提示。

Qt 的 ``QFileSystemWatcher`` 不递归，且不同平台对新建目录的行为不一致；
这里用轻量轮询（默认 800ms）换取确定性。插件源码规模通常很小，扫描成本
远低于一次错误的全量重载。
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

#: 不参与指纹的目录：版本库/缓存/虚拟环境
_EXCLUDED_DIRS = frozenset(
    {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
)
#: 不参与指纹的文件：字节码与临时文件
_EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".tmp", ".swp", ".log"})


def fingerprint_tree(root: Path) -> dict[str, tuple[int, int]]:
    """返回插件目录的稳定指纹：相对路径 -> (mtime_ns, size)。"""
    result: dict[str, tuple[int, int]] = {}
    base = Path(root)
    for current, dirs, files in os.walk(base):
        dirs[:] = [name for name in dirs if name not in _EXCLUDED_DIRS]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() in _EXCLUDED_SUFFIXES:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            result[str(path.relative_to(base))] = (stat.st_mtime_ns, stat.st_size)
    return result


class DevPluginWatcher(QObject):
    """轮询开发插件目录；变化时发出插件根目录路径。"""

    changed = Signal(str)

    def __init__(self, roots: Iterable[Path], *, interval_ms: int = 800, parent=None) -> None:
        super().__init__(parent)
        self._roots = [Path(item).resolve() for item in roots]
        self._fingerprints = {root: fingerprint_tree(root) for root in self._roots}
        self._timer = QTimer(self)
        self._timer.setInterval(max(100, int(interval_ms)))
        self._timer.timeout.connect(self.poll)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def poll(self) -> None:
        for root in self._roots:
            current = fingerprint_tree(root)
            if current == self._fingerprints.get(root, {}):
                continue
            self._fingerprints[root] = current
            self.changed.emit(str(root))

    def roots(self) -> tuple[Path, ...]:
        return tuple(self._roots)


__all__ = ["DevPluginWatcher", "fingerprint_tree"]
