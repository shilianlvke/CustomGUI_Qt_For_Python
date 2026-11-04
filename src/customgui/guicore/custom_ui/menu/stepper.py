"""步骤容器（Stepper）。

由「步骤条 + 内容栈 + 上一步/下一步/完成」组成，独立于 ``panels.CSteps``
实现：顶部步骤条横向排列，左侧步骤条纵向排列，配色同样实时读取调色板。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from customgui.appcore import AppSettings

from ..button import CButton, Variant
from ..paint_utils import draw_check
from .menu_list import menu_colors, menu_font

#: 步骤圆点直径（与 CSteps 一致）
CIRCLE_SIZE = 26
#: 横向步骤条高度 / 纵向步骤条宽度
STEP_BAR_HEIGHT = 52
STEP_BAR_WIDTH = 210
#: 纵向步骤条每行最小高度
STEP_ROW_HEIGHT = 56


def _stepper_config() -> tuple[int, int, int, int]:
    """(圆点直径, 步骤条高度, 步骤条宽度, 每行最小高度)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.menus
        return (
            int(cfg.stepper_circle_size),
            int(cfg.stepper_bar_height),
            int(cfg.stepper_bar_width),
            int(cfg.stepper_row_height),
        )
    except Exception:
        return CIRCLE_SIZE, STEP_BAR_HEIGHT, STEP_BAR_WIDTH, STEP_ROW_HEIGHT


def _normalize_steps(steps) -> list[dict]:
    """把字符串 / 字典 / ``(title, content)`` 归一为 step 字典。"""
    result: list[dict] = []
    for raw in steps or []:
        if isinstance(raw, dict):
            title = raw.get("title", raw.get("label", ""))
            content = raw.get("content")
        elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
            title, content = raw[0], raw[1]
        else:
            title, content = raw, None
        result.append({"title": str(title), "content": content})
    return result


class _StepIndicator(QWidget):
    """自绘步骤指示条（横向 / 纵向）。"""

    stepClicked = Signal(int)

    def __init__(self, orientation: str = "horizontal", parent=None):
        super().__init__(parent)
        (
            self._circle_size,
            self._step_bar_height,
            self._step_bar_width,
            self._step_row_height,
        ) = _stepper_config()
        self.setObjectName("CStepper_Indicator_Widget")
        self.setMouseTracking(True)
        self.setFont(menu_font(13))
        self._orientation = "vertical" if orientation == "vertical" else "horizontal"
        self._titles: list[str] = []
        self._current = 0
        self._hover = -1
        if self._orientation == "horizontal":
            self.setFixedHeight(self._step_bar_height)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedWidth(self._step_bar_width)
            self.setFixedHeight(self._step_row_height)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------
    def set_steps(self, titles: list[str], active: int | None = None) -> None:
        self._titles = list(titles)
        if active is not None and self._titles:
            self._current = max(0, min(int(active), len(self._titles) - 1))
        elif not self._titles:
            self._current = 0
        if self._orientation == "vertical":
            self.setFixedHeight(max(self._step_row_height * len(self._titles), self._step_row_height))
        self._hover = -1
        self.update()

    def set_current(self, index: int) -> None:
        if not self._titles:
            return
        self._current = max(0, min(int(index), len(self._titles) - 1))
        self.update()

    def current(self) -> int:
        return self._current

    def _block(self) -> float:
        if not self._titles:
            return 0.0
        return self.width() / len(self._titles) if self._orientation == "horizontal" else self.height() / len(self._titles)

    def _circle_rect(self, index: int) -> QRectF:
        block = self._block()
        if self._orientation == "horizontal":
            x = block * index + 2
            y = (self.height() - self._circle_size) / 2
        else:
            x = 2
            y = block * index + (block - self._circle_size) / 2
        return QRectF(x, y, self._circle_size, self._circle_size)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._titles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = menu_colors()
        metrics = QFontMetrics(self.font())
        number_font = QFont(self.font())
        number_font.setPixelSize(12)
        number_font.setWeight(QFont.Weight.DemiBold)

        for index, label in enumerate(self._titles):
            circle = self._circle_rect(index)
            completed = index < self._current
            active = index == self._current
            highlight = index == self._hover

            if index < len(self._titles) - 1:
                next_circle = self._circle_rect(index + 1)
                if self._orientation == "horizontal":
                    start = QPointF(circle.right(), circle.center().y())
                    end = QPointF(next_circle.left(), circle.center().y())
                else:
                    start = QPointF(circle.center().x(), circle.bottom())
                    end = QPointF(circle.center().x(), next_circle.top())
                painter.setPen(QPen(QColor(colors["accent"] if completed else colors["track"]), 2))
                painter.drawLine(start, end)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors["accent"] if completed or active else colors["background"]))
            painter.drawEllipse(circle)
            if not completed and not active:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(colors["accent"] if highlight else colors["track"]), 1.2))
                painter.drawEllipse(circle.adjusted(0.5, 0.5, -0.5, -0.5))

            if completed:
                draw_check(painter, circle.adjusted(7, 7, -7, -7), QColor(colors["on_accent"]), 2.0)
            else:
                painter.setFont(number_font)
                painter.setPen(QColor(colors["on_accent"] if active else colors["muted"]))
                painter.drawText(circle, Qt.AlignCenter, str(index + 1))

            if active or completed:
                text_color = colors["text"]
            elif highlight:
                text_color = colors["accent"]
            else:
                text_color = colors["muted"]
            painter.setFont(self.font())
            painter.setPen(QColor(text_color))

            if self._orientation == "horizontal":
                block = self._block()
                text_left = circle.right() + 8
                text_width = max(0.0, block - (text_left - block * index) - 8)
                text_rect = QRectF(text_left, 0, text_width, self.height())
                align = Qt.AlignVCenter | Qt.AlignLeft
            else:
                text_left = circle.right() + 8
                text_width = max(0.0, self.width() - text_left - 8)
                text_rect = QRectF(text_left, circle.top() - 4, text_width, circle.height() + 8)
                align = Qt.AlignVCenter | Qt.AlignLeft
            painter.drawText(
                text_rect,
                align,
                metrics.elidedText(label, Qt.ElideRight, int(text_width)),
            )
        painter.end()

    def _index_at(self, position) -> int:
        if not self._titles or self._block() <= 0:
            return -1
        if self._orientation == "horizontal":
            index = int(position.x() // self._block())
        else:
            index = int(position.y() // self._block())
        return max(0, min(index, len(self._titles) - 1))

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.setCursor(Qt.PointingHandCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.position())
            if index >= 0:
                self.stepClicked.emit(index)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        if self._orientation == "horizontal":
            return QSize(max(240, 120 * len(self._titles)), self._step_bar_height)
        return QSize(self._step_bar_width, max(self._step_row_height * len(self._titles), self._step_row_height))


class CStepper(QWidget):
    """步骤容器。

    Args:
        steps: 步骤列表，支持 ``"标题"``、``{"title": ..., "content": ...}``
            或 ``(标题, 内容)``；内容可以是字符串或 ``QWidget``。
        current: 初始步骤索引。
        position: ``"top"`` 顶部步骤条，``"left"`` 左侧步骤条。

    信号：
        ``stepChanged(int)``：当前步骤变化；
        ``finished()``：在最后一步点击「完成」（或直接调用 ``finish``）。
    """

    stepChanged = Signal(int)
    finished = Signal()

    def __init__(self, steps=None, current: int = 0, position: str = "top", parent=None):
        super().__init__(parent)
        self.setObjectName("CStepper_Widget")
        self._position = "left" if str(position).lower() in ("left", "vertical") else "top"
        self._steps: list[dict] = []
        self._owned: list[QWidget] = []
        self._current = -1

        self._bar = _StepIndicator("vertical" if self._position == "left" else "horizontal", self)
        self._stack = QStackedWidget(self)
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._prev_button = CButton("上一步", variant=Variant.OUTLINED, size="sm")
        self._prev_button.setObjectName("CStepper_Prev_Button")
        self._next_button = CButton("下一步", size="sm")
        self._next_button.setObjectName("CStepper_Next_Button")

        self._build_layout()
        self._bar.stepClicked.connect(self.set_current)
        self._prev_button.clicked.connect(self.previous_step)
        self._next_button.clicked.connect(self.next_step)
        self.set_steps(steps or [], current=current)

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)
        footer.addWidget(self._prev_button)
        footer.addWidget(self._next_button)

        if self._position == "top":
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            layout.addWidget(self._bar)
            layout.addWidget(self._stack, 1)
            layout.addLayout(footer)
            return

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._bar, 0, Qt.AlignTop)
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._stack, 1)
        right_layout.addLayout(footer)
        layout.addWidget(right, 1)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_steps(self, steps, current: int | None = None) -> None:
        """替换全部步骤；不会触发 ``stepChanged``。"""
        self._clear_contents()
        self._steps = _normalize_steps(steps)
        for step in self._steps:
            widget, owned = self._materialize_content(step["content"])
            self._stack.addWidget(widget)
            if owned:
                self._owned.append(widget)
        target = self._current if current is None else int(current)
        self._current = self._clamp(target) if self._steps else -1
        self._sync()

    def add_step(self, title: str, content=None) -> int:
        """追加一个步骤并返回其索引。"""
        self._steps.append({"title": str(title), "content": content})
        widget, owned = self._materialize_content(content)
        self._stack.addWidget(widget)
        if owned:
            self._owned.append(widget)
        if self._current < 0:
            self._current = 0
        self._sync()
        return len(self._steps) - 1

    def steps(self) -> list[dict]:
        return [{"title": step["title"], "content": step["content"]} for step in self._steps]

    def step_titles(self) -> list[str]:
        return [step["title"] for step in self._steps]

    def step_count(self) -> int:
        return len(self._steps)

    def step_content(self, index: int) -> QWidget | None:
        if 0 <= index < self._stack.count():
            return self._stack.widget(index)
        return None

    def current_index(self) -> int:
        return self._current

    def position(self) -> str:
        return self._position

    @property
    def prev_button(self) -> CButton:
        """「上一步」按钮（供外层禁用/定制）。"""
        return self._prev_button

    @property
    def next_button(self) -> CButton:
        """「下一步 / 完成」按钮。"""
        return self._next_button

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------
    def set_current(self, index: int) -> None:
        """跳转到指定步骤；索引变化时发出 ``stepChanged``。"""
        if not self._steps:
            return
        target = self._clamp(index)
        if target == self._current:
            return
        self._current = target
        self._sync()
        self.stepChanged.emit(target)

    def previous_step(self) -> None:
        if self._current > 0:
            self.set_current(self._current - 1)

    def next_step(self) -> None:
        if not self._steps:
            return
        if self._current < len(self._steps) - 1:
            self.set_current(self._current + 1)
        else:
            self.finish()

    def finish(self) -> None:
        """跳到末步（如尚未到达）并发出 ``finished``。"""
        if not self._steps:
            return
        last = len(self._steps) - 1
        if self._current != last:
            self.set_current(last)
        self.finished.emit()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _clamp(self, index: int) -> int:
        if not self._steps:
            return -1
        return max(0, min(int(index), len(self._steps) - 1))

    def _materialize_content(self, content) -> tuple[QWidget, bool]:
        if isinstance(content, QWidget):
            return content, False
        label = QLabel("" if content is None else str(content))
        label.setObjectName("CStepper_Content_Label")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setContentsMargins(4, 4, 4, 4)
        label.setStyleSheet(f"color: {menu_colors()['text']};")
        return label, True

    def _clear_contents(self) -> None:
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            if widget in self._owned:
                self._owned.remove(widget)
                widget.deleteLater()
            else:
                widget.setParent(None)

    def _sync(self) -> None:
        active = max(0, self._current)
        self._bar.set_steps(self.step_titles(), active=active)
        self._stack.setCurrentIndex(active)
        self._sync_navigation()

    def _sync_navigation(self) -> None:
        has_steps = bool(self._steps)
        self._prev_button.setEnabled(has_steps and self._current > 0)
        self._next_button.setEnabled(has_steps)
        last = has_steps and self._current == len(self._steps) - 1
        self._next_button.setText("完成" if last else "下一步")


__all__ = ["CStepper", "STEP_BAR_HEIGHT", "STEP_BAR_WIDTH"]
