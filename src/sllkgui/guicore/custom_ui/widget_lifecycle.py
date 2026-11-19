"""控件脱离与释放的通用工具。

Qt 的 ``QWidget.setParent(None)`` 会把控件变成**顶层窗口**：一个可见的控件在
失去父级后，Qt 会自动把它显示出来。此刻它就成了一个无标题的、脱离宿主的小
窗口——用户看到的是「点了某个栏目后一闪而过的小窗」。

这不是 Qt 的 bug，而是「可见 widget 被 setParent(None)」的固有行为。因此凡是
「把可见控件从布局里摘下来」的地方，都必须先 ``hide()``。

本模块提供两个入口：

- :func:`detach` —— 安全脱离（先隐藏，再解除父子关系）
- :func:`clear_layout` —— 清空布局里的全部控件

两者都保持「不销毁控件」的语义：调用方仍持有控件引用时，控件不会被析构，只
是脱离出对象树。真正要销毁的用 ``deleteLater()``。
"""

from __future__ import annotations

from PySide6.QtWidgets import QLayout, QWidget


def detach(widget: QWidget | None) -> None:
    """把控件脱离父级，但不让它闪现成顶层窗口。

    ``widget`` 为 ``None`` 时直接返回，便于在清理循环里无条件调用。
    """
    if widget is None:
        return
    # 必须先隐藏：setParent(None) 会让控件成为顶层窗口，Qt 会自动显示它。
    # 顺序反了就会闪现一个小窗口。
    widget.hide()
    widget.setParent(None)


def clear_layout(layout: QLayout | None) -> list[QWidget]:
    """清空布局，返回被摘下来的控件（保持存活，不销毁）。

    控件已先 ``hide()``，因此不会在脱离瞬间闪现成顶层窗口。
    """
    if layout is None:
        return []
    detached: list[QWidget] = []
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is None:
            continue
        widget.hide()
        widget.setParent(None)
        detached.append(widget)
    return detached


__all__ = ["clear_layout", "detach"]
