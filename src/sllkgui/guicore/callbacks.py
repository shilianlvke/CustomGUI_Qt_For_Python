"""Qt 回调守卫：让「页面销毁后仍被后台信号回调」不再产生噪音。

问题背景
--------
页面常因语言切换、窗口重建等原因被销毁；后台线程（如 :mod:`task` 的任务）
仍在运行，其排队回调随后会触碰已经不存在的 Qt 控件，抛出
``RuntimeError: Internal C++ object already deleted``。这类错误无害但会刷屏。

本模块把「识别已删除控件错误 + 静默跳过 + 其余异常记录」收敛成一组工具，
供表现层组件统一使用。
"""

from __future__ import annotations

from collections.abc import Callable

from sllkgui.appcore import Logger


def is_deleted_qt_error(exc: BaseException) -> bool:
    """判断异常是否只是「C++ 对象已被销毁」。"""
    message = str(exc)
    return "Internal C++ object" in message or "has been deleted" in message


def safe_callback(callback: Callable):
    """包装回调：已删除控件引发的错误静默跳过，其余异常记录后返回 ``None``。

    不会让异常向上冒泡到 Qt 事件循环（那会中断一批本可继续的刷新）。
    """

    def invoke(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except RuntimeError as exc:
            if is_deleted_qt_error(exc):
                Logger.debug(f"Ignoring callback for deleted widget: {exc}")
                return None
            raise
        except Exception as exc:  # noqa: BLE001 - 回调异常不应打断事件循环
            Logger.exception(f"UI callback failed: {exc}")
            return None

    return invoke


def ui_callback(owner, callback: Callable):
    """包装 hub 信号槽：宿主对象已销毁时直接跳过，不再执行回调。

    *owner* 是回调所属的 Qt 对象（如页面）。优先用 ``shiboken6.isValid``
    做前置判断，避免在已删除对象上做任何操作；没有 shiboken6 时退化为
    :func:`safe_callback`。
    """
    guarded = safe_callback(callback)
    try:
        import shiboken6
    except ImportError:
        return guarded

    def invoke(*args, **kwargs):
        if not shiboken6.isValid(owner):
            return None
        return guarded(*args, **kwargs)

    return invoke


def single_shot(owner, msec: int, callback: Callable) -> None:
    """``QTimer.singleShot`` 的宿主安全版：宿主销毁后自动失效。"""
    from PySide6.QtCore import QTimer

    try:
        import shiboken6
    except ImportError:
        QTimer.singleShot(msec, safe_callback(callback))
        return

    def invoke():
        if not shiboken6.isValid(owner):
            return
        safe_callback(callback)()

    QTimer.singleShot(msec, invoke)


__all__ = ["is_deleted_qt_error", "safe_callback", "single_shot", "ui_callback"]
