import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .logger_module import Logger

# 遥测写入使用进程内互斥锁，避免并发写文件时数据竞争。
_LOCK = threading.Lock()

# FIX-08: events.jsonl 大小轮转阈值（1 MiB）与备份后缀，只保留 1 份备份。
# 阈值足够大，普通会话不会触发轮转，read_recent_events() 与 limit 查询不受影响。
MAX_EVENT_FILE_BYTES = 1_048_576
EVENT_BACKUP_SUFFIX = ".1"

# 遥测属于「尽力而为」能力：写失败只降级记录一次日志，
# 绝不向上抛出而影响主程序运行。
_write_failure_reported = False


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串。"""
    return datetime.now(UTC).isoformat()


def _resolve_diagnostics_dir() -> Path:
    """解析遥测目录，统一由 ``current_config().resolved_diagnostics_dir()`` 决定。"""
    from sllkgui.config import current_config

    configured = current_config().resolved_diagnostics_dir()
    path = Path(configured)
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


def _rotate_event_file_if_needed(event_path: Path) -> None:
    """FIX-08: events.jsonl 达到阈值时重命名为 .1（覆盖旧备份），只保留 1 份。

    轮转失败按「尽力而为」处理：不向上抛，继续写入当前文件。
    """
    try:
        if not event_path.is_file() or event_path.stat().st_size < MAX_EVENT_FILE_BYTES:
            return
        backup = event_path.with_name(event_path.name + EVENT_BACKUP_SUFFIX)
        os.replace(event_path, backup)  # 覆盖已有 .1，始终只保留 1 份备份
    except OSError:
        return


def _append_event(payload: dict):
    """追加单条事件到 events.jsonl；写入前按需轮转旧文件。"""
    event_path = _event_file_path()
    _rotate_event_file_if_needed(event_path)
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


def _notify_write_failure(scope: str, exc: Exception):
    """写失败降级：每个会话只记录一次错误日志，避免刷屏。"""
    global _write_failure_reported
    if not _write_failure_reported:
        _write_failure_reported = True
        Logger.error(f"遥测数据写入失败({scope})，本次会话不再重试: {exc}")


def record_event(name: str, category: str = "app", level: str = "info", payload: dict | None = None):
    """记录一条遥测事件并更新聚合指标。

    参数:
    - name: 事件名
    - category: 事件分类
    - level: 严重级别（仅记录，不做过滤）
    - payload: 事件附加数据

    写入失败（磁盘满/权限不足等）不会抛出异常，
    仅降级为一次错误日志，保证遥测不影响主程序。
    """
    event_payload = {
        "timestamp": _utc_now_iso(),
        "name": name,
        "category": category,
        "level": level,
        "payload": payload or {},
    }
    with _LOCK:
        try:
            _append_event(event_payload)
            _update_metrics(name=name, category=category)
        except (OSError, TypeError, ValueError) as exc:
            # FIX-08: 覆盖 json.dumps 的 TypeError 与 int() 的 ValueError，
            # 保留「尽力而为、不影响主流程」语义。
            _notify_write_failure("events/metrics", exc)


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
