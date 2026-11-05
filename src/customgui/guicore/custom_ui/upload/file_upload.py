"""文件上传组件（复刻 PrimeVue FileUpload 的 advanced / basic 两种形态）。

实现约定：

1. **不联网**：组件只负责本地文件的选择、校验与列表维护；``custom_upload=True``
   时提供一个本地进度演示接口（``start_upload`` 用定时器推进进度并发出信号），
   真实上传由调用方在 ``uploadStarted`` 之后自行接管；
2. 颜色全部取自 :func:`~..display.palette.tokens`，拖放区自绘、文件行随主题重绘，
   切换主题后无需重建组件即可生效；
3. 文件校验顺序为「是否存在 → 后缀 → 大小」，任何一项失败都发出
   ``fileRejected(path, reason)``，并给出状态文字 / 内联错误提示。
"""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from customgui.appcore import AppSettings

from ...acrylic import glass_surface
from ..button.button import CButton
from ..button.severity import Severity, Variant, severity_color
from ..display.palette import tokens
from ..display.progress import CProgressBar
from ..feedback.message import CMessage

#: 拖放区圆角
_RADIUS = 8
#: 文件列表最大高度
_LIST_MAX_HEIGHT = 200
#: 进度演示的刷新间隔（毫秒）与每次增量
_UPLOAD_INTERVAL_MS = 60
_UPLOAD_STEP = 5


def _upload_config() -> tuple[int, int, int, int]:
    """(圆角, 列表最大高度, 进度刷新间隔, 每次增量)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.upload
        return (
            int(cfg.radius),
            int(cfg.list_max_height),
            int(cfg.upload_interval),
            int(cfg.upload_step),
        )
    except Exception:
        return _RADIUS, _LIST_MAX_HEIGHT, _UPLOAD_INTERVAL_MS, _UPLOAD_STEP


def _format_size(size: int) -> str:
    """把字节数格式化成易读文本。"""
    value = float(max(0, int(size)))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _normalize_accept(accept) -> set[str]:
    """把 ``accept`` 归一成 ``{".png", ".jpg"}`` 形式的后缀集合。

    支持 ``".png,.jpg"``、``["png", "*.jpg"]``、``"*"``（不过滤）等写法。
    """
    if not accept:
        return set()
    if isinstance(accept, str):
        parts = accept.replace(";", ",").split(",")
    else:
        parts = list(accept)
    suffixes: set[str] = set()
    for part in parts:
        value = str(part).strip().lower()
        if not value:
            continue
        if value == "*":
            return set()
        if value.startswith("*."):
            value = value[1:]
        if not value.startswith("."):
            value = "." + value
        suffixes.add(value)
    return suffixes


class _DropArea(QFrame):
    """自绘拖放区：虚线边框、上传箭头、拖入时高亮。"""

    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._radius = _upload_config()[0]
        self.setObjectName("CFileUpload_DropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drag_active = False

    # ------------------------------------------------------------------
    # 拖放
    # ------------------------------------------------------------------
    def _has_local_files(self, mime) -> bool:
        if not mime.hasUrls():
            return False
        return any(url.isLocalFile() for url in mime.urls())

    def dragEnterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._has_local_files(event.mimeData()):
            self._drag_active = True
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._drag_active = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._drag_active = False
        self.update()
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = tokens()
        accent = QColor(palette["accent"])
        border = accent if self._drag_active else QColor(palette["border"])
        # 拖放区是页面上的大块表面：跟随亚克力强度，避免在玻璃卡片上留下
        # 一整块不透明底；拖入时仍用强调色淡底强调交互状态。
        background = glass_surface(palette["surface"], AppSettings.glass.card, minimum=0.10)
        if self._drag_active:
            background = QColor(accent)
            background.setAlpha(28)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(path, background)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 1.4, Qt.DashLine))
        painter.drawPath(path)

        center_x = rect.center().x()
        arrow_y = rect.center().y() - 28
        painter.setPen(QPen(accent, 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(center_x, arrow_y + 10), QPointF(center_x, arrow_y - 10))
        painter.drawLine(QPointF(center_x, arrow_y - 10), QPointF(center_x - 7, arrow_y - 3))
        painter.drawLine(QPointF(center_x, arrow_y - 10), QPointF(center_x + 7, arrow_y - 3))

        font = QFont(self.font())
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette["text"]))
        painter.drawText(
            QRectF(rect.left(), arrow_y + 20, rect.width(), 24),
            Qt.AlignCenter,
            "将文件拖放到此处",
        )

        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(palette["muted"]))
        painter.drawText(
            QRectF(rect.left(), arrow_y + 46, rect.width(), 22),
            Qt.AlignCenter,
            "或点击选择文件",
        )
        painter.end()


class _ElidingLabel(QLabel):
    """按当前宽度省略中间字符的标签（文件名/标题用）。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = str(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        QLabel.setText(self, self._full_text)
        self.setToolTip(self._full_text)

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._full_text = str(text)
        self._refresh()
        self.setToolTip(self._full_text)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.ElideMiddle, max(0, self.width())
        )
        QLabel.setText(self, elided)


class _FileRow(QFrame):
    """已选文件的一行：文件名、大小、移除按钮。"""

    removed = Signal(str)

    def __init__(self, path: str, size: int, parent=None):
        super().__init__(parent)
        self._path = path
        self.setObjectName("CFileUpload_Row")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(8)

        self._name_label = _ElidingLabel(os.path.basename(path), self)
        self._name_label.setToolTip(path)

        self._size_label = QLabel(_format_size(size), self)
        self._size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._remove_button = CButton(
            "×",
            severity=Severity.DANGER,
            variant=Variant.TEXT,
            size="sm",
            fixed_width=30,
            parent=self,
        )
        self._remove_button.setToolTip("移除该文件")
        self._remove_button.clicked.connect(lambda: self.removed.emit(self._path))

        layout.addWidget(self._name_label, 1)
        layout.addWidget(self._size_label, 0)
        layout.addWidget(self._remove_button, 0)
        self._apply_colors()

    def _apply_colors(self) -> None:
        if not hasattr(self, "_name_label"):
            return
        palette = tokens()
        self._name_label.setStyleSheet(f"color: {palette['text']}; background: transparent;")
        self._size_label.setStyleSheet(f"color: {palette['muted']}; background: transparent;")
        self.update()

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_colors()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, QColor(palette["surface"]))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)
        painter.end()


class CFileUpload(QWidget):
    """文件上传控件（PrimeVue FileUpload 风格）。

    参数:
        mode: ``"advanced"``（拖放区 + 文件列表 + 进度）或 ``"basic"``
            （紧凑选择按钮 + 状态 + 进度）。
        accept: 允许的后缀，例如 ``".png,.jpg"`` / ``["png", "jpg"]``；
            为空表示不限制。
        multiple: 是否允许一次选择多个文件。
        max_file_size: 单文件最大字节数，``None`` 表示不限制。
        custom_upload: ``False`` 时只收集文件，``start_upload`` 不推进进度；
            ``True`` 时提供本地进度演示。
        parent: 父控件。

    信号:
        filesSelected(list[str]): 当前已选文件列表发生变化（新增或移除后）。
        uploadStarted(): 进度演示开始。
        uploadProgress(int): 进度 0~100。
        uploadFinished(list[str]): 进度演示完成时的文件列表。
        fileRejected(str, str): 被拒绝的文件路径与原因。
    """

    filesSelected = Signal(list)
    uploadStarted = Signal()
    uploadProgress = Signal(int)
    uploadFinished = Signal(list)
    fileRejected = Signal(str, str)

    def __init__(
        self,
        mode: str = "advanced",
        accept=None,
        multiple: bool = True,
        max_file_size: int | None = None,
        custom_upload: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        _, self._list_max_height, self._upload_interval, self._upload_step = _upload_config()
        self.setObjectName("CFileUpload_Widget")
        self._mode = "basic" if str(mode).strip().lower() == "basic" else "advanced"
        self._accept = _normalize_accept(accept)
        self._multiple = bool(multiple)
        self._max_file_size = None if max_file_size is None else max(0, int(max_file_size))
        self._custom_upload = bool(custom_upload)
        self._files: list[str] = []
        self._rows: dict[str, _FileRow] = {}
        self._progress_value = 0
        self._upload_files: list[str] = []
        self._status_is_error = False

        self._upload_timer = QTimer(self)
        self._upload_timer.setInterval(self._upload_interval)
        self._upload_timer.timeout.connect(self._on_upload_tick)

        self._build_ui()
        self._apply_colors()
        self.set_status("尚未选择文件")
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._status_label = QLabel(self)
        self._status_label.setObjectName("CFileUpload_Status")
        self._status_label.setWordWrap(True)

        self._message = CMessage(simple=True, severity="danger", parent=self)
        self._message.setVisible(False)

        self._progress = CProgressBar(height=6, parent=self)
        self._progress.setVisible(self._custom_upload)

        if self._mode == "advanced":
            self._drop_area: _DropArea | None = _DropArea(self)
            self._drop_area.filesDropped.connect(self.add_files)
            self._drop_area.clicked.connect(self.select_files)
            root.addWidget(self._drop_area)

            self._list_host = QWidget(self)
            self._rows_layout = QVBoxLayout(self._list_host)
            self._rows_layout.setContentsMargins(0, 0, 0, 0)
            self._rows_layout.setSpacing(4)
            self._rows_layout.setAlignment(Qt.AlignTop)

            self._list_scroll = QScrollArea(self)
            self._list_scroll.setObjectName("CFileUpload_ListScroll")
            self._list_scroll.setWidgetResizable(True)
            self._list_scroll.setFrameShape(QFrame.NoFrame)
            self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._list_scroll.setMaximumHeight(self._list_max_height)
            self._list_scroll.setWidget(self._list_host)
            self._list_scroll.setVisible(False)
            root.addWidget(self._list_scroll)

            root.addWidget(self._progress)
            root.addWidget(self._message)
            root.addWidget(self._status_label)
        else:
            self._drop_area = None
            self._list_host = None
            self._list_scroll = None
            self._rows_layout = None
            self._choose_button = CButton("选择文件", size="sm", parent=self)
            self._choose_button.clicked.connect(self.select_files)

            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            header.addWidget(self._choose_button, 0)
            header.addWidget(self._status_label, 1)
            root.addLayout(header)
            root.addWidget(self._progress)
            root.addWidget(self._message)

    def _apply_colors(self) -> None:
        palette = tokens()
        color = QColor(severity_color(Severity.DANGER)) if self._status_is_error else QColor(palette["muted"])
        self._status_label.setStyleSheet(f"color: {color.name()}; background: transparent;")

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_colors()
            if self._drop_area is not None:
                self._drop_area.update()
            for row in self._rows.values():
                row._apply_colors()

    # ------------------------------------------------------------------
    # 文件选择
    # ------------------------------------------------------------------
    def select_files(self) -> None:
        """打开系统文件对话框并收集选中的文件。"""
        filter_text = self._dialog_filter()
        if self._multiple:
            paths, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", filter_text)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter_text)
            paths = [path] if path else []
        if paths:
            self.add_files(paths)

    def _dialog_filter(self) -> str:
        if not self._accept:
            return "所有文件 (*)"
        patterns = " ".join(sorted(f"*{suffix}" for suffix in self._accept))
        return f"文件 ({patterns});;所有文件 (*)"

    def _key(self, path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

    def add_files(self, paths) -> None:
        """把一批路径加入已选列表，逐条校验并发出相应信号。

        这是拖放、文件对话框与程序化添加共用的入口，测试可直接调用。
        """
        if isinstance(paths, (str, os.PathLike)):
            paths = [paths]

        accepted: list[str] = []
        rejected: list[tuple[str, str]] = []
        for raw in paths:
            path = os.fspath(raw)
            if not path:
                continue
            key = self._key(path)
            if not os.path.isfile(path):
                rejected.append((path, "文件不存在或不可读"))
            elif key in self._rows or any(self._key(item) == key for item in self._files):
                rejected.append((path, "文件已添加"))
            elif self._accept and os.path.splitext(path)[1].lower() not in self._accept:
                allowed = "、".join(sorted(self._accept))
                rejected.append((path, f"不支持的文件类型（允许：{allowed}）"))
            elif self._max_file_size is not None and os.path.getsize(path) > self._max_file_size:
                rejected.append((path, f"文件大小超过限制（最大 {_format_size(self._max_file_size)}）"))
            else:
                self._files.append(path)
                accepted.append(path)
                if self._mode == "advanced":
                    self._append_row(path)

        for path, reason in rejected:
            self.fileRejected.emit(path, reason)

        if accepted:
            self._message.setVisible(False)
            suffix = f"，{len(rejected)} 个被拒绝" if rejected else ""
            self.set_status(f"已选择 {len(self._files)} 个文件{suffix}")
            self.filesSelected.emit(list(self._files))
        elif rejected:
            self._show_rejection(rejected[-1][1])

    def _append_row(self, path: str) -> None:
        if self._rows_layout is None:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        row = _FileRow(path, size, self._list_host)
        row.removed.connect(self.remove_file)
        self._rows[self._key(path)] = row
        self._rows_layout.addWidget(row)
        if self._list_scroll is not None:
            self._list_scroll.setVisible(True)

    def remove_file(self, path: str) -> None:
        """从已选列表中移除一个文件。"""
        key = self._key(path)
        for index, existing in enumerate(self._files):
            if self._key(existing) == key:
                self._files.pop(index)
                break
        row = self._rows.pop(key, None)
        if row is not None:
            if self._rows_layout is not None:
                self._rows_layout.removeWidget(row)
            row.deleteLater()
        if self._list_scroll is not None:
            self._list_scroll.setVisible(bool(self._files))
        self.set_status(f"已选择 {len(self._files)} 个文件" if self._files else "尚未选择文件")
        self.filesSelected.emit(list(self._files))

    def clear_files(self) -> None:
        """清空全部已选文件。"""
        for row in self._rows.values():
            if self._rows_layout is not None:
                self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._files.clear()
        if self._list_scroll is not None:
            self._list_scroll.setVisible(False)
        self.set_status("尚未选择文件")
        self.filesSelected.emit([])

    def files(self) -> list[str]:
        """当前已选文件路径列表。"""
        return list(self._files)

    def file_count(self) -> int:
        return len(self._files)

    def set_accept(self, accept) -> None:
        """更新允许的后缀集合（用法同构造参数 ``accept``）。"""
        self._accept = _normalize_accept(accept)

    def set_max_file_size(self, max_file_size: int | None) -> None:
        """更新单文件大小上限（字节，``None`` 表示不限）。"""
        self._max_file_size = None if max_file_size is None else max(0, int(max_file_size))

    # ------------------------------------------------------------------
    # 进度 / 状态 / 演示上传
    # ------------------------------------------------------------------
    def set_progress(self, value: int) -> None:
        """设置进度（0~100）并发出 ``uploadProgress``。"""
        progress = max(0, min(100, int(value)))
        self._progress_value = progress
        self._progress.setValue(progress)
        self.uploadProgress.emit(progress)

    def progress(self) -> int:
        return self._progress_value

    def set_status(self, text: str) -> None:
        """设置状态文本（常规颜色）。"""
        self._status_is_error = False
        self._status_label.setText(str(text))
        self._apply_colors()

    def status_text(self) -> str:
        return self._status_label.text()

    def _show_rejection(self, reason: str) -> None:
        self._status_is_error = True
        self._status_label.setText(reason)
        self._apply_colors()
        self._message.set_text(reason)
        self._message.setVisible(True)

    def start_upload(self) -> None:
        """本地进度演示：不联网，只按定时器推进 0~100。"""
        if not self._files:
            self.set_status("请先选择文件")
            return
        if not self._custom_upload:
            self.set_status(f"已收集 {len(self._files)} 个文件（custom_upload=False，未执行上传）")
            return
        self._upload_files = list(self._files)
        self._progress.setVisible(True)
        self.set_progress(0)
        self.set_status("上传中…")
        self.uploadStarted.emit()
        self._upload_timer.start()

    def cancel_upload(self) -> None:
        self._upload_timer.stop()
        if self._progress_value < 100:
            self.set_status("上传已取消")

    def is_uploading(self) -> bool:
        return self._upload_timer.isActive()

    def _on_upload_tick(self) -> None:
        progress = min(100, self._progress_value + self._upload_step)
        self.set_progress(progress)
        if progress >= 100:
            self._upload_timer.stop()
            self.set_status("上传完成")
            self.uploadFinished.emit(list(self._upload_files))

    # ------------------------------------------------------------------
    # 拖放（basic 模式没有拖放区，由控件本身接收）
    # ------------------------------------------------------------------
    def _has_local_files(self, mime) -> bool:
        return mime.hasUrls() and any(url.isLocalFile() for url in mime.urls())

    def dragEnterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._mode == "basic" and self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._mode != "basic":
            event.ignore()
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_files(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(460, 320) if self._mode == "advanced" else QSize(360, 96)


__all__ = ["CFileUpload"]
