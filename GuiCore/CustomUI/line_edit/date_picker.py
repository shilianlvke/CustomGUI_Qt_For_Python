"""日期选择：日历面板（``CCalendarPanel``）+ 下拉日期框（``CDatePicker``）。"""

from __future__ import annotations

from PySide6.QtCore import QDate, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..button import CButton
from .dropdown import CDropdownField
from .input_style import colors, field_font
from .paint_utils import draw_calendar, draw_chevron

CELL = 36
WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
HEADER_HEIGHT = 34
WEEKDAY_HEIGHT = 24


class CCalendarPanel(QWidget):
    """月历面板：上/下月切换、日期点选、今天高亮。"""

    selectionChanged = Signal(QDate)

    def __init__(self, value: QDate | None = None, parent=None):
        super().__init__(parent)
        self._value = value or QDate.currentDate()
        self._view = QDate(self._value.year(), self._value.month(), 1)
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(field_font("md"))
        self.setFixedSize(CELL * 7 + 8, HEADER_HEIGHT + WEEKDAY_HEIGHT + CELL * 6 + 4)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def date(self) -> QDate:
        return self._value

    def set_date(self, value: QDate) -> None:
        self._value = value
        self._view = QDate(value.year(), value.month(), 1)
        self.update()

    def month_offset(self, months: int) -> None:
        self._view = self._view.addMonths(months)
        self.update()

    def _grid_rect(self) -> QRectF:
        return QRectF(4, HEADER_HEIGHT + WEEKDAY_HEIGHT, CELL * 7, CELL * 6)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accent = QColor(palette["focus_border"])

        # 头部：‹ 月份 年份 ›
        painter.setPen(QColor(palette["text"]))
        header_font = QFont(self.font())
        header_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(header_font)
        title = f"{self._view.toString('MMMM')} {self._view.year()}"
        painter.drawText(QRectF(0, 0, self.width(), HEADER_HEIGHT), Qt.AlignCenter, title)
        painter.setFont(self.font())
        draw_chevron(painter, QPointF(16, HEADER_HEIGHT / 2), palette["text"], 8, "left", 1.6)
        draw_chevron(painter, QPointF(self.width() - 16, HEADER_HEIGHT / 2), palette["text"], 8, "right", 1.6)

        # 星期表头
        weekday_font = QFont(self.font())
        weekday_font.setPixelSize(12)
        painter.setFont(weekday_font)
        painter.setPen(QColor(palette["placeholder"]))
        for column, label in enumerate(WEEKDAYS):
            painter.drawText(
                QRectF(4 + column * CELL, HEADER_HEIGHT, CELL, WEEKDAY_HEIGHT),
                Qt.AlignCenter,
                label,
            )
        painter.setFont(self.font())

        grid = self._grid_rect()
        leading = self._view.dayOfWeek() - 1
        days = self._view.daysInMonth()
        today = QDate.currentDate()

        for day in range(1, days + 1):
            index = leading + day - 1
            row, column = divmod(index, 7)
            center = QPointF(grid.left() + column * CELL + CELL / 2, grid.top() + row * CELL + CELL / 2)
            radius = CELL / 2 - 4
            date = QDate(self._view.year(), self._view.month(), day)

            if date == self._value:
                painter.setBrush(accent)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, radius, radius)
                painter.setPen(QColor("#ffffff"))
            elif date == today:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(accent), 1.2))
                painter.drawEllipse(center, radius, radius)
                painter.setPen(QColor(accent))
            else:
                painter.setPen(QColor(palette["text"]))

            if index == self._hover and date != self._value:
                fill = QColor(palette["hover_border"])
                fill.setAlpha(34)
                painter.setBrush(fill)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, radius, radius)
                painter.setPen(QColor(palette["text"]))

            painter.drawText(
                QRectF(center.x() - CELL / 2, center.y() - CELL / 2, CELL, CELL),
                Qt.AlignCenter,
                str(day),
            )
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _day_at(self, position) -> QDate | None:
        grid = self._grid_rect()
        if not grid.contains(position):
            return None
        column = int((position.x() - grid.left()) // CELL)
        row = int((position.y() - grid.top()) // CELL)
        index = row * 7 + column - (self._view.dayOfWeek() - 1)
        if not 0 <= index < self._view.daysInMonth():
            return None
        return QDate(self._view.year(), self._view.month(), index + 1)

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        date = self._day_at(event.position())
        index = date.day() if date is not None else -1
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        position = event.position()
        if position.y() <= HEADER_HEIGHT:
            if position.x() < 32:
                self.month_offset(-1)
            elif position.x() > self.width() - 32:
                self.month_offset(1)
            return
        date = self._day_at(position)
        if date is not None:
            self._value = date
            self.update()
            self.selectionChanged.emit(date)


class CDatePicker(CDropdownField):
    """日期下拉框：显示 yyyy-MM-dd，弹出月历 + 今天/清除按钮。"""

    dateChanged = Signal(object)

    def __init__(
        self,
        value: QDate | None = None,
        placeholder: str = "Select Date",
        size: str = "md",
        show_button_bar: bool = True,
        parent=None,
    ):
        super().__init__(placeholder, size, chevron=False, parent=parent)
        self._value = value
        self._show_button_bar = show_button_bar
        self._panel: CCalendarPanel | None = None

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def date(self) -> QDate | None:
        return self._value

    def set_date(self, value: QDate | None, emit: bool = True) -> None:
        self._value = value
        self.update()
        if emit:
            self.dateChanged.emit(value)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        self._paint_box(painter)
        text = self._value.toString("yyyy-MM-dd") if self._value is not None else ""
        painter.setPen(QColor(palette["text"] if text else palette["placeholder"]))
        metrics = QFontMetrics(self.font())
        rect = QRectF(self._text_left(), 0, self.width() - self._text_left() - 30, self.height())
        painter.drawText(
            rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            metrics.elidedText(text or self._placeholder, Qt.ElideRight, int(rect.width())),
        )
        icon_rect = QRectF(self.width() - 24, self.height() / 2 - 8, 15, 15)
        draw_calendar(painter, icon_rect, palette["icon"], 1.3)
        painter.end()

    # ------------------------------------------------------------------
    # 弹层
    # ------------------------------------------------------------------
    def _popup_width(self) -> int:
        return max(self.width(), 272)

    def _build_popup(self) -> QWidget | None:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._panel = CCalendarPanel(self._value, holder)
        self._panel.selectionChanged.connect(self._choose)
        layout.addWidget(self._panel)

        if self._show_button_bar:
            bar = QHBoxLayout()
            bar.setContentsMargins(4, 0, 4, 2)
            today = CButton(text="Today", variant="text", size="sm", parent=holder)
            today.clicked.connect(self._choose_today)
            clear = CButton(text="Clear", variant="text", size="sm", parent=holder)
            clear.clicked.connect(self._clear)
            bar.addWidget(today)
            bar.addStretch()
            bar.addWidget(clear)
            layout.addLayout(bar)
        return holder

    def _choose(self, value: QDate) -> None:
        self._value = value
        self.close_popup()
        self.update()
        self.dateChanged.emit(value)

    def _choose_today(self) -> None:
        self._choose(QDate.currentDate())

    def _clear(self) -> None:
        self._value = None
        if self._panel is not None:
            self._panel.set_date(QDate.currentDate())
        self.close_popup()
        self.update()
        self.dateChanged.emit(None)


__all__ = ["CDatePicker", "CCalendarPanel"]
