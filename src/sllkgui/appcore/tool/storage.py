"""原子化 JSON / 文本持久化工具（反哺自 PyCL2 的 ``jsonstore``）。

特点
----
- **原子替换**：先写同目录临时文件，``flush`` + ``os.fsync`` 落盘后
  ``os.replace`` 原子替换，崩溃不会留下半个文件；
- **可选备份**：写入前把旧文件复制为 ``.bak``，损坏时自动回退；
- **线程安全**：写操作由一把 ``RLock`` 串行化；
- **零第三方依赖**：纯标准库，可被逻辑层/表现层安全引用。

对比 PyCL2 原版
---------------
原版依赖 ``sllkgui.appcore.record_event``，事件名写死 ``pycl2.data.*``。
搬进基座后事件名去品牌化为 ``data.recovered`` / ``data.corrupt``，日志
统一走 ``Logger``，文案改为中文。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from sllkgui.appcore import Logger, record_event


class StoreError(RuntimeError):
    """持久化数据无法读取或写入时抛出。"""


#: 所有写操作共用一把锁（进程内串行化，避免并发写坏文件）
_LOCK = threading.RLock()


def read_json(path: str | Path, default: Any = None) -> Any:
    """读取 JSON 文件；不存在返回 *default*；损坏时尝试 ``.bak`` 回退。

    回退失败或备份也损坏时抛出 :class:`StoreError`（不静默吞掉，
    让调用方明确知道数据已损坏，而不是把空数据当有效结果）。
    """
    file = Path(path)
    if not file.is_file():
        return default
    try:
        with file.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        Logger.warning(f"数据文件读取失败，尝试备份：{file}（{exc}）")
        backup = file.with_suffix(file.suffix + ".bak")
        if backup.is_file():
            try:
                with backup.open("r", encoding="utf-8-sig") as handle:
                    data = json.load(handle)
                Logger.warning(f"已从备份恢复数据文件：{backup}")
                record_event(
                    "data.recovered",
                    category="data",
                    level="warn",
                    payload={"file": file.name, "backup": backup.name, "error": str(exc)},
                )
                return data
            except (OSError, ValueError) as backup_exc:
                Logger.error(f"备份文件同样无法读取：{backup}（{backup_exc}）")
        Logger.error(f"数据文件损坏且无可用备份：{file}")
        record_event(
            "data.corrupt",
            category="data",
            level="error",
            payload={"file": file.name, "error": str(exc)},
        )
        raise StoreError(f"无法读取数据文件 {file}: {exc}") from exc


def write_json(path: str | Path, data: Any, *, backup: bool = True) -> None:
    """原子写 JSON。

    先在同目录写临时文件并 ``fsync``，再 ``os.replace`` 原子替换；
    写入失败清理临时文件并原样抛出异常。
    """
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        if backup and file.is_file():
            try:
                shutil.copy2(file, file.with_suffix(file.suffix + ".bak"))
            except OSError as exc:
                Logger.warning(f"创建备份失败（继续写入）：{file}（{exc}）")
        fd, tmp_name = tempfile.mkstemp(prefix=f".{file.name}.", suffix=".tmp", dir=str(file.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, file)
            Logger.debug(f"数据已写入：{file}")
        except Exception as exc:
            Logger.error(f"数据写入失败：{file}（{exc}）")
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def read_text(path: str | Path, default: str = "") -> str:
    """读取文本文件；不存在返回 *default*；读取失败静默回落默认值。"""
    file = Path(path)
    if not file.is_file():
        return default
    try:
        return file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default


def write_text(path: str | Path, text: str) -> None:
    """原子写文本文件（与 :func:`write_json` 同样的落盘语义）。"""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{file.name}.", suffix=".tmp", dir=str(file.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, file)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


__all__ = ["StoreError", "read_json", "write_json", "read_text", "write_text"]
