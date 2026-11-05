"""流体布局包装（Windows Fluent Design Fluid：子控件随容器宽度伸缩）。"""

from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


class CFluid(QWidget):
    """纵向排列、宽度自适应的轻量容器。

    ``add_widget`` 把子控件的水平尺寸策略改为 ``Expanding``，容器变宽时
    子控件跟着变宽；``set_content`` 用于只放一个主内容部件的场景。
    """

    def __init__(self, content: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._content: QWidget | None = None
        if content is not None:
            self.set_content(content)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """把子控件加入容器并允许其水平方向伸缩。"""
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        widget.setSizePolicy(policy)
        self._layout.addWidget(widget, stretch)

    def set_content(self, widget: QWidget | None) -> None:
        """替换容器里的全部内容（只保留一个主内容部件）。"""
        self.clear()
        self._content = widget
        if widget is not None:
            self.add_widget(widget, 1)

    def content(self) -> QWidget | None:
        return self._content

    def widgets(self) -> list[QWidget]:
        return [self._layout.itemAt(index).widget() for index in range(self._layout.count())]

    def clear(self) -> None:
        """移除并释放所有子控件（不销毁由调用方持有的主内容）。"""
        while self._layout.count():
            entry = self._layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.setParent(None)
        self._content = None


__all__ = ["CFluid"]
