"""模块说明。"""

import json
import os
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

# 遥测写入使用进程内互斥锁，避免并发写文件时数据竞争。
_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    """获取当前 UTC 时间字符串。

    返回:
    - str: ISO8601 格式时间文本。
    """
    return datetime.now(UTC).isoformat()


def _resolve_diagnostics_dir() -> Path:
    """解析遥测输出目录。

    职责:
    - 优先读取环境变量 ``CUSTOMGUI_DIAGNOSTICS_DIR``。
    - 未设置时回落到项目 ``logs/diagnostics`` 目录。
    - 确保目录存在。

    返回:
    - Path: 可写入的遥测目录路径。
    """
    custom_dir = os.getenv("CUSTOMGUI_DIAGNOSTICS_DIR", "").strip()
    path = Path(custom_dir) if custom_dir else Path(__file__).resolve().parents[3] / "logs" / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _event_file_path() -> Path:
    """获取事件日志文件路径。

    返回:
    - Path: ``events.jsonl`` 文件路径。
    """
    return _resolve_diagnostics_dir() / "events.jsonl"


def _metric_file_path() -> Path:
    """获取指标聚合文件路径。

    返回:
    - Path: ``metrics.json`` 文件路径。
    """
    return _resolve_diagnostics_dir() / "metrics.json"


def _safe_dump_json(path: Path, data: dict[str, object]) -> None:
    """将 JSON 数据安全写入文件。

    参数:
    - path: 目标文件路径。
    - data: 待写入的字典数据。

    返回:
    - None
    """
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_metrics(path: Path) -> dict:
    """读取指标聚合文件。

    参数:
    - path: 指标文件路径。

    返回:
    - dict: 指标字典；文件不存在或损坏时返回默认结构。
    """
    if not path.exists():
        return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}
    try:
        content = path.read_text(encoding="utf-8")
        loaded = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}
    else:
        if not isinstance(loaded, dict):
            return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}
        loaded.setdefault("events", {})
        loaded.setdefault("categories", {})
        loaded.setdefault("updated_at", _utc_now_iso())
        return loaded


def _append_event(payload: dict[str, object]) -> None:
    """追加单条事件到日志文件。

    参数:
    - payload: 事件对象。

    返回:
    - None
    """
    event_path = _event_file_path()
    line = json.dumps(payload, ensure_ascii=False)
    with event_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _update_metrics(name: str, category: str) -> None:
    """更新指标计数聚合。

    参数:
    - name: 事件名称。
    - category: 事件分类。

    返回:
    - None
    """
    metric_path = _metric_file_path()
    metrics = _read_metrics(metric_path)
    metrics["events"][name] = int(metrics["events"].get(name, 0)) + 1
    metrics["categories"][category] = int(metrics["categories"].get(category, 0)) + 1
    metrics["updated_at"] = _utc_now_iso()
    _safe_dump_json(metric_path, metrics)


def record_event(
    name: str,
    category: str = "app",
    level: str = "info",
    payload: dict[str, object] | None = None,
) -> None:
    """记录一条遥测事件并更新聚合指标。

    参数:
    - name: 事件名称。
    - category: 事件分类。
    - level: 严重级别（仅记录，不做过滤）。
    - payload: 事件附加数据。

    返回:
    - None
    """
    event_payload = {
        "timestamp": _utc_now_iso(),
        "name": name,
        "category": category,
        "level": level,
        "payload": payload or {},
    }
    with _LOCK:
        _append_event(event_payload)
        _update_metrics(name=name, category=category)


@contextmanager
def track_timing(
    name: str,
    category: str = "perf",
    payload: dict[str, object] | None = None,
) -> Generator[None, None, None]:
    """上下文计时器。

    参数:
    - name: 计时事件名称。
    - category: 事件分类，默认 ``perf``。
    - payload: 附加事件数据。

    返回:
    - contextmanager: 可用于 ``with`` 语句的计时上下文。
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        base = payload or {}
        merged = dict(base)
        merged["duration_ms"] = elapsed_ms
        record_event(name=name, category=category, level="info", payload=merged)


def read_recent_events(limit: int = 20) -> list[dict]:
    """读取最近事件列表。

    参数:
    - limit: 最大返回条数。

    返回:
    - list[dict]: 最近事件集合，按写入顺序返回末尾片段。
    """
    if limit <= 0:
        return []
    path = _event_file_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    result = []
    for line in lines[-limit:]:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
