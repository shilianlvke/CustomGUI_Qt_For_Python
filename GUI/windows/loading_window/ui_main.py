from PySide6.QtWidgets import QWidget, QHBoxLayout, QProgressBar
from PySide6.QtCore import Qt, QPropertyAnimation, QThreadPool, Signal, Property
from AppCore import Logger
from .functions import LoadingTask, ResourceLoader


class Loading(QWidget):
	stopRequested = Signal()

	def __init__(self, image_path=None):
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

	def get_value(self):
		return self._value

	def set_value(self, value):
		self._value = max(0, min(100, int(value)))
		self._progress.setValue(self._value)

	value = Property(int, get_value, set_value)


class LoadingWindow(QWidget):
	loaded = Signal(bool)

	def __init__(self, image_path):
		super().__init__()
		Logger.tool(__class__)
		self.dragging = False
		self.offset = None

		layout = QHBoxLayout()
		self.setLayout(layout)
		self.progress = Loading(image_path)
		self.progress.stopRequested.connect(self.handle_stop)
		layout.addWidget(self.progress)

		self.setWindowFlag(Qt.FramelessWindowHint)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self.setStyleSheet("background: transparent;")
		self.setFixedSize(self.progress.size())

		self.quit_anim = QPropertyAnimation(self.progress, b"value", self)
		self.quit_anim.setDuration(300)
		self.quit_anim.finished.connect(self.thread_stop)

		self.thread_pool = QThreadPool.globalInstance()
		self.loader = ResourceLoader()
		self._task_started = False

		self.load_anim = QPropertyAnimation(self.progress, b"value", self)
		self.load_anim.setDuration(10)
		self.load_anim.finished.connect(lambda: self.loader.resume())

		self.setup_loading()

	def setup_loading(self):
		self.loader.bus.progress_updated.connect(self.update_progress)
		self.loader.bus.finished.connect(self.open_main_window)
		self.loader.bus.error_occurred.connect(self.handle_error)

	def update_progress(self, value):
		self.load_anim.setStartValue(self.progress.get_value())
		self.load_anim.setEndValue(value)
		self.load_anim.start()
		# self.progress.set_value(value)

	def open_main_window(self):
		self.loaded.emit(True)
		self.close()

	def handle_error(self, message):
		Logger.error(message)
		self.close()

	def handle_stop(self):
		self.quit_anim.setStartValue(self.progress.get_value())
		self.quit_anim.setEndValue(0)
		self.loader.stop()
		self.quit_anim.start()

	def thread_stop(self):
		self.loader.stop()
		self.close()

	def showEvent(self, event):
		if not self._task_started:
			self._task_started = True
			self.thread_pool.start(LoadingTask(self.loader))
		super().showEvent(event)

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			self.dragging = True
			self.offset = event.globalPosition().toPoint() - self.pos()

	def mouseMoveEvent(self, event):
		if self.dragging and self.offset:
			self.move(event.globalPosition().toPoint() - self.offset)

	def mouseReleaseEvent(self, event):
		self.dragging = False


__all__ = ["Loading", "LoadingWindow"]
