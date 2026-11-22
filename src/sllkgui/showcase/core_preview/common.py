"""组件预览插件的共享日志桥。

预览页里的控件回调需要记录日志，但工厂只在构建时拿到 ``ctx``；这里保存
当前上下文，页面统一调用 :func:`log` / :func:`toast`，由基座注入插件前缀与
统一的提示通道（预览页因此不需要自己算标题栏偏移）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from sllkgui.plugin import GalleryContext

_ctx: GalleryContext | None = None


def bind_context(ctx: GalleryContext) -> None:
    global _ctx
    _ctx = ctx


def log(message: str, level: str = "info") -> None:
    if _ctx is None:
        return
    _ctx.log(str(message), level)


def toast() -> Any | None:
    """插件上下文里的 toast 通道；未绑定上下文时返回 ``None``。"""
    return getattr(_ctx, "toast", None)


__all__ = ["bind_context", "log", "toast"]
