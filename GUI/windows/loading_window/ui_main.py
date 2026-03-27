"""模块说明。"""

from typing import override

from PySide6.QtCore import Property, QPropertyAnimation, Qt, QThreadPool, Signal
from PySide6.QtGui import QMouseEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QWidget

from AppCore import Logger

from .functions import LoadingTask, ResourceLoader


class Loading(QWidget):
    """加载进度展示组件。"""

    stop_requested = Signal()

    def __init__(self, image_path: str | None = None) -> None:
        """初始化加载进度组件。"""
        super().__init__()
        self._image_path = image_path
        self._value = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(False)
        self._progress.setValue(self._value)
        self._progress.setFixedSize(320, 14)
        layout.addWidget(self._progress)

    def get_value(self) -> int:
        """获取当前进度值。"""
        return self._value

    def set_value(self, value: int) -> None:
        """设置当前进度值。"""
        self._value = max(0, min(100, int(value)))
        self._progress.setValue(self._value)

    value = Property(int, get_value, set_value)


class LoadingWindow(QWidget):
    """应用启动加载窗口。"""

    loaded = Signal(bool)

    def __init__(self, image_path: str | None) -> None:
        """初始化加载窗口。"""
        super().__init__()
        Logger.tool(__class__)
        self.dragging = False
        self.offset = None

        layout = QHBoxLayout()
        self.setLayout(layout)
        self.progress = Loading(image_path)
        self.progress.stop_requested.connect(self.handle_stop)
        layout.addWidget(self.progress)

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(self.progress.size())

        self.quit_anim = QPropertyAnimation(self.progress, b"value", self)
        self.quit_anim.setDuration(300)
        self.quit_anim.finished.connect(self.thread_stop)

        self.thread_pool = QThreadPool.globalInstance()
        self.loader = ResourceLoader()
        self._task_started = False

        self.load_anim = QPropertyAnimation(self.progress, b"value", self)
        self.load_anim.setDuration(10)
        self.load_anim.finished.connect(self.loader.resume)

        self.setup_loading()

    def setup_loading(self) -> None:
        """绑定加载过程信号。"""
        self.loader.bus.progress_updated.connect(self.update_progress)
        self.loader.bus.finished.connect(self.open_main_window)
        self.loader.bus.error_occurred.connect(self.handle_error)

    def update_progress(self, value: int) -> None:
        """更新进度动画值。"""
        self.load_anim.setStartValue(self.progress.get_value())
        self.load_anim.setEndValue(value)
        self.load_anim.start()

    def open_main_window(self) -> None:
        """加载完成后关闭窗口。"""
        loaded_ok = True
        self.loaded.emit(loaded_ok)
        self.close()

    def handle_error(self, message: str) -> None:
        """处理加载错误。"""
        Logger.error(message)
        self.close()

    def handle_stop(self) -> None:
        """处理外部停止请求。"""
        self.quit_anim.setStartValue(self.progress.get_value())
        self.quit_anim.setEndValue(0)
        self.loader.stop()
        self.quit_anim.start()

    def thread_stop(self) -> None:
        """停止加载线程并关闭窗口。"""
        self.loader.stop()
        self.close()

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """显示时启动异步加载任务。"""
        if not self._task_started:
            self._task_started = True
            self.thread_pool.start(LoadingTask(self.loader))
        super().showEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """记录拖拽起点。"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.globalPosition().toPoint() - self.pos()

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """处理窗口拖拽。"""
        if self.dragging and self.offset:
            self.move(event.globalPosition().toPoint() - self.offset)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """结束窗口拖拽。"""
        _ = event
        self.dragging = False


__all__ = ["Loading", "LoadingWindow"]
