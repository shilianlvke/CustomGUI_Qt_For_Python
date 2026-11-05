"""回调守卫与后台任务测试。"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from sllkgui.guicore import (
    ProgressUpdate,
    TaskWorker,
    active_tasks,
    is_deleted_qt_error,
    run_task,
    safe_callback,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# --------------------------------------------------------------------------
# 回调守卫
# --------------------------------------------------------------------------
def test_is_deleted_qt_error_recognises_signature():
    assert is_deleted_qt_error(RuntimeError("Internal C++ object already deleted"))
    assert is_deleted_qt_error(RuntimeError("wrapped C/C++ object has been deleted"))
    assert not is_deleted_qt_error(RuntimeError("some other error"))


def test_safe_callback_swallows_deleted_error():
    calls = []

    def cb():
        calls.append(1)
        raise RuntimeError("Internal C++ object already deleted")

    wrapped = safe_callback(cb)
    assert wrapped() is None
    assert calls == [1]


def test_safe_callback_returns_value():
    wrapped = safe_callback(lambda: 42)
    assert wrapped() == 42


def test_safe_callback_logs_other_errors_and_returns_none():
    def cb():
        raise ValueError("boom")

    assert safe_callback(cb)() is None


# --------------------------------------------------------------------------
# ProgressUpdate
# --------------------------------------------------------------------------
def test_progress_percent_prefers_fraction():
    assert ProgressUpdate(fraction=0.42).percent == 42


def test_progress_percent_falls_back_to_current_total():
    assert ProgressUpdate(current=1, total=4).percent == 25


def test_progress_percent_zero_when_no_data():
    assert ProgressUpdate().percent == 0


def test_progress_percent_clamped():
    assert ProgressUpdate(fraction=1.5).percent == 100
    assert ProgressUpdate(fraction=-0.5).percent == 0


# --------------------------------------------------------------------------
# 后台任务
# --------------------------------------------------------------------------
def test_run_task_delivers_finished_result(qapp):
    owner = QObject()
    done = []

    worker = run_task(owner, lambda emit: 42, on_done=done.append, name="calc")
    assert worker in active_tasks()
    # 等待线程池执行完成
    deadline = time.monotonic() + 5
    while not done and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    assert done == [42]
    assert worker not in active_tasks()


def test_run_task_delivers_error(qapp):
    owner = QObject()
    errors = []

    def fail(_emit):
        raise RuntimeError("boom")

    worker = run_task(owner, fail, on_error=errors.append, name="fail")
    deadline = time.monotonic() + 5
    while not errors and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    assert len(errors) == 1
    assert "boom" in errors[0]
    assert worker not in active_tasks()


def test_run_task_progress(qapp):
    owner = QObject()
    updates = []

    def work(emit):
        emit(ProgressUpdate(fraction=0.5, message="half"))
        return "done"

    worker = run_task(owner, work, on_progress=updates.append, name="prog")
    deadline = time.monotonic() + 5
    while worker in active_tasks() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    assert updates
    assert updates[0].percent == 50


def test_task_worker_signals_are_worker_signals_type(qapp):
    worker = TaskWorker(lambda emit: None, name="x")
    assert worker.cancelled is False
    worker.cancel()
    assert worker.cancelled is True


def test_active_tasks_returns_frozenset(qapp):
    assert isinstance(active_tasks(), frozenset)
