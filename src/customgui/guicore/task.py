"""后台任务基础设施：``QRunnable`` 封装 + 进度事件 + 宿主生命周期管理。

反哺自 PyCL2 的 ``TaskWorker`` / ``run_task``，解决了几个 Qt 线程常见坑：

1. **宿主销毁后信号不炸**：回调统一走 :mod:`callbacks.safe_callback`；
2. **任务追踪**：每个 ``owner`` 挂一组 ``_workers``，宿主可随时拿到在跑的
   任务；全局 ``active_tasks()`` 供诊断/退出时批量取消；
3. **取消协议**：``cancel_callback`` + ``cancelled`` 信号，取消后不再派发
   ``finished``；
4. **信号发射兜底**：窗口销毁后 ``signal.emit`` 可能抛 ``RuntimeError``，
   统一吞掉，不让后台线程崩溃。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from customgui.appcore import Logger

from .callbacks import safe_callback


@dataclass
class ProgressUpdate:
    """中立的进度事件（可被任何后台任务复用）。"""

    stage: str = ""
    message: str = ""
    current: int = 0
    total: int = 0
    fraction: float = 0.0
    detail: str = ""
    done: bool = False

    @property
    def percent(self) -> int:
        """整体进度百分比。``fraction`` 优先于 ``current/total``。

        用 ``current/total`` 时它们通常描述「当前子阶段」（如下载单个文件），
        不能驱动外层总进度条，否则会在真正结束前就显示 100%。
        """
        if self.fraction > 0:
            return max(0, min(100, int(self.fraction * 100)))
        if self.total > 0:
            return max(0, min(100, int(self.current * 100 / self.total)))
        return 0


class WorkerSignals(QObject):
    """后台任务的四类信号。"""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class TaskWorker(QRunnable):
    """可取消的后台任务。

    ``fn(progress_emit)`` 在 ``QThreadPool`` 线程里执行，``progress_emit``
    是 ``self.signals.progress.emit`` 的便捷引用。
    """

    def __init__(self, fn: Callable[[Callable[[ProgressUpdate], None]], Any], *, name: str = ""):
        super().__init__()
        self.fn = fn
        self.name = name
        self.signals = WorkerSignals()
        self.cancel_callback: Callable[[], None] | None = None
        self.cancelled = False
        self.setAutoDelete(True)

    def cancel(self) -> None:
        """请求取消：置位并调用可选的外部取消回调。"""
        self.cancelled = True
        if self.cancel_callback:
            try:
                self.cancel_callback()
            except Exception:  # noqa: BLE001 - 取消回调失败不影响主流程
                pass

    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit)
            if self.cancelled:
                self._safe_emit(self.signals.cancelled)
            else:
                self._safe_emit(self.signals.finished, result)
        except Exception as exc:  # noqa: BLE001 - 后台异常转为 failed 信号
            Logger.exception(f"后台任务失败 {self.name}: {exc}")
            if self.cancelled:
                self._safe_emit(self.signals.cancelled)
            else:
                self._safe_emit(self.signals.failed, str(exc))

    @staticmethod
    def _safe_emit(signal, *args) -> None:
        """窗口销毁后 emit 可能抛 RuntimeError，吞掉即可。"""
        try:
            signal.emit(*args)
        except RuntimeError:
            pass


#: 全局活跃任务集合（诊断、退出时批量取消）
_ACTIVE_TASKS: set[TaskWorker] = set()


def active_tasks() -> frozenset[TaskWorker]:
    """返回当前活跃任务的快照。"""
    return frozenset(_ACTIVE_TASKS)


def run_task(
    owner,
    fn: Callable[[Callable[[ProgressUpdate], None]], Any],
    *,
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    on_progress: Callable[[ProgressUpdate], None] | None = None,
    on_cancelled: Callable[[], None] | None = None,
    name: str = "",
    cancel_callback: Callable[[], None] | None = None,
    pool: QThreadPool | None = None,
) -> TaskWorker:
    """在后台线程执行 ``fn``，并把结果/进度桥接回宿主线程。

    *owner* 是发起任务的 Qt 对象（如页面）；任务结束自动从 ``owner._workers``
    与全局集合中移除。
    """
    worker = TaskWorker(fn, name=name)
    worker.cancel_callback = cancel_callback

    workers = getattr(owner, "_workers", None)
    if workers is None:
        workers = set()
        owner._workers = workers
    workers.add(worker)
    _ACTIVE_TASKS.add(worker)

    started_at = time.monotonic()

    def cleanup() -> None:
        workers.discard(worker)
        _ACTIVE_TASKS.discard(worker)
        Logger.debug(f"后台任务结束：{name or 'task'}（{time.monotonic() - started_at:.3f}s）")

    if on_progress:
        worker.signals.progress.connect(safe_callback(on_progress))
    if on_done:
        worker.signals.finished.connect(safe_callback(on_done))
    if on_error:
        worker.signals.failed.connect(safe_callback(on_error))
    if on_cancelled:
        worker.signals.cancelled.connect(safe_callback(on_cancelled))
    worker.signals.finished.connect(lambda _result: cleanup())
    worker.signals.failed.connect(lambda _error: cleanup())
    worker.signals.cancelled.connect(cleanup)

    Logger.debug(f"后台任务启动：{name or 'task'}")
    (pool or QThreadPool.globalInstance()).start(worker)
    return worker


__all__ = [
    "ProgressUpdate",
    "TaskWorker",
    "WorkerSignals",
    "active_tasks",
    "run_task",
]
