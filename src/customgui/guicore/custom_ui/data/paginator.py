"""分页器（复刻 PrimeVue Aura Paginator）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..button import CButton
from ..line_edit import CSelect


class CPaginator(QWidget):
    """页码导航：首页 / 上一页 / 页码 / 下一页 / 末页 + 每页条数。"""

    pageChanged = Signal(int)
    pageSizeChanged = Signal(int)

    def __init__(
        self,
        page: int = 0,
        page_count: int = 1,
        page_size: int = 10,
        page_sizes: tuple[int, ...] = (5, 10, 20, 50),
        total: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CPaginator_Widget")
        self._page = 0
        self._page_count = 1
        self._page_size = max(1, int(page_size))
        self._page_sizes = tuple(sorted({max(1, int(size)) for size in page_sizes}))
        self._total = max(0, int(total))
        self._buttons: list[CButton] = []
        self._updating = False
        self._rebuild_pending = False
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.timeout.connect(self._rebuild_page_buttons)
        self._setup_ui()
        self.set_state(page, page_count, page_size, total)
        # 构造期没有用户输入，直接建一次页码，避免首帧空白
        if self._rebuild_pending:
            self._rebuild_page_buttons()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)

        self._page_size_select = CSelect(
            options=[str(size) for size in self._page_sizes],
            value=str(self._page_size),
            size="sm",
            parent=self,
        )
        self._page_size_select.setFixedWidth(78)
        self._page_size_select.selectionChanged.connect(self._on_page_size_selected)
        layout.addWidget(self._page_size_select, 0, Qt.AlignVCenter)

        self._first = self._nav_button("«", "First page")
        self._prev = self._nav_button("", "Previous page", icon="icon_arrow_left")
        layout.addWidget(self._first)
        layout.addWidget(self._prev)

        self._page_layout = QHBoxLayout()
        self._page_layout.setContentsMargins(0, 0, 0, 0)
        self._page_layout.setSpacing(4)
        layout.addLayout(self._page_layout)

        self._next = self._nav_button("", "Next page", icon="icon_arrow_right")
        self._last = self._nav_button("»", "Last page")
        layout.addWidget(self._next)
        layout.addWidget(self._last)

        layout.addStretch(1)

        self._report = QLabel(self)
        self._report.setObjectName("CPaginator_Label")
        self._report.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._report)

        self._first.clicked.connect(lambda: self.set_page(0, emit=True))
        self._prev.clicked.connect(lambda: self.set_page(self._page - 1, emit=True))
        self._next.clicked.connect(lambda: self.set_page(self._page + 1, emit=True))
        self._last.clicked.connect(lambda: self.set_page(self._page_count - 1, emit=True))

    def _nav_button(self, text: str, tooltip: str, icon=None) -> CButton:
        button = CButton(
            text,
            icon=icon,
            size="sm",
            variant="text",
            severity="secondary",
            fixed_width=32 if not text else 36,
            parent=self,
        )
        button.setToolTip(tooltip)
        return button

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def page(self) -> int:
        return self._page

    def page_count(self) -> int:
        return self._page_count

    def page_size(self) -> int:
        return self._page_size

    def total(self) -> int:
        return self._total

    def set_state(self, page: int, page_count: int, page_size: int, total: int) -> None:
        """整体刷新分页状态（不触发信号）。"""
        self._updating = True
        self._total = max(0, int(total))
        if self._total == 0:
            # 空结果时没有“第 1 页”可高亮，也不应允许翻页。
            self._page_count = 0
            self._page = 0
        else:
            self._page_count = max(1, int(page_count))
            self._page = max(0, min(int(page), self._page_count - 1))
        self._page_size = max(1, int(page_size))
        if str(self._page_size) not in self._page_size_select.options():
            self._page_sizes = tuple(sorted({*self._page_sizes, self._page_size}))
            self._page_size_select.set_options([str(size) for size in self._page_sizes], keep_value=False)
        self._page_size_select.set_value(str(self._page_size), emit=False)
        has_pages = self._total > 0 and self._page_count > 0
        self._first.setEnabled(has_pages and self._page > 0)
        self._prev.setEnabled(has_pages and self._page > 0)
        self._next.setEnabled(has_pages and self._page < self._page_count - 1)
        self._last.setEnabled(has_pages and self._page < self._page_count - 1)
        self._schedule_rebuild()
        start = self._page * self._page_size + 1 if self._total else 0
        end = min(self._total, (self._page + 1) * self._page_size)
        self._report.setText(f"{start}-{end} / {self._total}")
        self._updating = False

    def set_page(self, page: int, emit: bool = True) -> None:
        if self._page_count <= 0:
            return
        page = max(0, min(int(page), self._page_count - 1))
        if page == self._page:
            return
        self._page = page
        self._first.setEnabled(page > 0)
        self._prev.setEnabled(page > 0)
        self._next.setEnabled(page < self._page_count - 1)
        self._last.setEnabled(page < self._page_count - 1)
        self._schedule_rebuild()
        start = self._page * self._page_size + 1 if self._total else 0
        end = min(self._total, (self._page + 1) * self._page_size)
        self._report.setText(f"{start}-{end} / {self._total}")
        if emit:
            self.pageChanged.emit(self._page)

    def set_page_size(self, page_size: int, emit: bool = True) -> None:
        page_size = max(1, int(page_size))
        if page_size == self._page_size:
            return
        self._page_size = page_size
        if str(page_size) not in self._page_size_select.options():
            self._page_sizes = tuple(sorted({*self._page_sizes, page_size}))
            self._page_size_select.set_options([str(size) for size in self._page_sizes], keep_value=False)
        self._page_size_select.set_value(str(page_size), emit=False)
        self.set_page(0, emit=emit)
        if emit:
            self.pageSizeChanged.emit(page_size)

    def _on_page_size_selected(self, value) -> None:
        if self._updating or value is None:
            return
        self.set_page_size(int(value), emit=True)

    def _schedule_rebuild(self) -> None:
        """延到下一轮事件循环重建页码。

        页码按钮的 ``clicked`` 会走到 ``set_page``，若在信号栈内立即删除
        当前 sender，CButton 的动画/重绘回调会访问已析构的 C++ 对象，表现为
        点击分页闪退。延迟重建可保证信号处理先完整返回。
        """
        if self._rebuild_pending:
            return
        self._rebuild_pending = True
        self._rebuild_timer.start(0)

    def _rebuild_page_buttons(self) -> None:
        self._rebuild_pending = False
        self._rebuild_timer.stop()
        # 页码窗口：当前页保持在中间，最多 5 个；空结果不显示页码。
        if self._page_count <= 0:
            pages = []
        elif self._page_count <= 7:
            pages = list(range(self._page_count))
        else:
            start = max(0, min(self._page - 2, self._page_count - 5))
            pages = list(range(start, start + 5))

        # 多余的按钮延迟删除；已有按钮优先复用，避免翻页时删除刚点击的 sender
        while len(self._buttons) > len(pages):
            button = self._buttons.pop()
            self._page_layout.removeWidget(button)
            button.hide()
            button.deleteLater()

        for slot, index in enumerate(pages):
            digits = len(str(self._page_count))
            width = max(32, 18 + digits * 7)
            if slot < len(self._buttons):
                button = self._buttons[slot]
                button.setText(str(index + 1))
                button.set_variant("solid" if index == self._page else "text")
                button.set_severity("primary" if index == self._page else "secondary")
            else:
                button = CButton(
                    str(index + 1),
                    size="sm",
                    variant="solid" if index == self._page else "text",
                    severity="primary" if index == self._page else "secondary",
                    fixed_width=width,
                    parent=self,
                )
                button.clicked.connect(self._on_page_button_clicked)
                self._page_layout.addWidget(button)
                self._buttons.append(button)
            button.setFixedWidth(width)
            button.setProperty("pageIndex", index)

    def _on_page_button_clicked(self) -> None:
        button = self.sender()
        if button is None:
            return
        index = button.property("pageIndex")
        if index is not None:
            self.set_page(int(index), emit=True)


__all__ = ["CPaginator"]
