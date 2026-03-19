import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


# 遥测写入使用进程内互斥锁，避免并发写文件时数据竞争。
_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _resolve_diagnostics_dir() -> Path:
    """解析遥测目录。

    优先使用环境变量 CUSTOMGUI_DIAGNOSTICS_DIR，
    未设置时回落到项目 logs/diagnostics 目录。
    """
    custom_dir = os.getenv("CUSTOMGUI_DIAGNOSTICS_DIR", "").strip()
    if custom_dir:
        path = Path(custom_dir)
    else:
        path = Path(__file__).resolve().parents[3] / "logs" / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _event_file_path() -> Path:
    """事件日志文件路径（JSON Lines）。"""
    return _resolve_diagnostics_dir() / "events.jsonl"


def _metric_file_path() -> Path:
    """指标聚合文件路径（JSON）。"""
    return _resolve_diagnostics_dir() / "metrics.json"


def _safe_dump_json(path: Path, data: dict):
    """统一 JSON 落盘，保持 UTF-8 与可读缩进。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_metrics(path: Path) -> dict:
    """读取指标文件；损坏或不存在时返回默认结构。"""
    if not path.exists():
        return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}
    try:
        content = path.read_text(encoding="utf-8")
        loaded = json.loads(content)
        if not isinstance(loaded, dict):
            return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}
        loaded.setdefault("events", {})
        loaded.setdefault("categories", {})
        loaded.setdefault("updated_at", _utc_now_iso())
        return loaded
    except (OSError, json.JSONDecodeError):
        return {"updated_at": _utc_now_iso(), "events": {}, "categories": {}}


def _append_event(payload: dict):
    """追加单条事件到 events.jsonl。"""
    event_path = _event_file_path()
    line = json.dumps(payload, ensure_ascii=False)
    with event_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _update_metrics(name: str, category: str):
    """更新事件名与分类维度计数。"""
    metric_path = _metric_file_path()
    metrics = _read_metrics(metric_path)
    metrics["events"][name] = int(metrics["events"].get(name, 0)) + 1
    metrics["categories"][category] = int(metrics["categories"].get(category, 0)) + 1
    metrics["updated_at"] = _utc_now_iso()
    _safe_dump_json(metric_path, metrics)


def record_event(name: str, category: str = "app", level: str = "info", payload: dict | None = None):
    """记录一条遥测事件并更新聚合指标。

    参数:
    - name: 事件名
    - category: 事件分类
    - level: 严重级别（仅记录，不做过滤）
    - payload: 事件附加数据
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
def track_timing(name: str, category: str = "perf", payload: dict | None = None):
    """上下文计时器。

    用法:
        with track_timing("loading.total"):
            ...
    退出上下文后会自动记录 duration_ms。
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
    """读取最近 N 条事件，按写入顺序返回末尾片段。"""
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
