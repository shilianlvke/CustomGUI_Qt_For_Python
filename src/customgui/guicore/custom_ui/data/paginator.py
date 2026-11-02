"""分页器（复刻 PrimeVue Aura Paginator）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
        self._setup_ui()
        self.set_state(page, page_count, page_size, total)

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
        self._page_count = max(1, int(page_count))
        self._page = max(0, min(int(page), self._page_count - 1))
        self._page_size = max(1, int(page_size))
        self._total = max(0, int(total))
        if str(self._page_size) not in self._page_size_select.options():
            self._page_sizes = tuple(sorted({*self._page_sizes, self._page_size}))
            self._page_size_select.set_options([str(size) for size in self._page_sizes], keep_value=False)
        self._page_size_select.set_value(str(self._page_size), emit=False)
        self._first.setEnabled(self._page > 0)
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < self._page_count - 1)
        self._last.setEnabled(self._page < self._page_count - 1)
        self._rebuild_page_buttons()
        start = self._page * self._page_size + 1 if self._total else 0
        end = min(self._total, (self._page + 1) * self._page_size)
        self._report.setText(f"{start}-{end} / {self._total}")
        self._updating = False

    def set_page(self, page: int, emit: bool = True) -> None:
        page = max(0, min(int(page), self._page_count - 1))
        if page == self._page:
            return
        self._page = page
        self._first.setEnabled(page > 0)
        self._prev.setEnabled(page > 0)
        self._next.setEnabled(page < self._page_count - 1)
        self._last.setEnabled(page < self._page_count - 1)
        self._rebuild_page_buttons()
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

    def _rebuild_page_buttons(self) -> None:
        for button in self._buttons:
            self._page_layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()

        # 页码窗口：当前页保持在中间，最多 5 个
        if self._page_count <= 7:
            pages = list(range(self._page_count))
        else:
            start = max(0, min(self._page - 2, self._page_count - 5))
            pages = list(range(start, start + 5))

        for index in pages:
            button = CButton(
                str(index + 1),
                size="sm",
                variant="solid" if index == self._page else "text",
                severity="primary" if index == self._page else "secondary",
                fixed_width=32,
                parent=self,
            )
            button.clicked.connect(lambda _=False, i=index: self.set_page(i, emit=True))
            self._page_layout.addWidget(button)
            self._buttons.append(button)


__all__ = ["CPaginator"]
