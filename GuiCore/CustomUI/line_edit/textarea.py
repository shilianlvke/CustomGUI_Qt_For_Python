"""多行输入框（复刻 PrimeVue Aura Textarea）。"""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy

from .input_style import RADIUS, corner_css, size_spec


class CTextarea(QPlainTextEdit):
    """Aura 风格多行输入框，支持随内容自动增高。

    颜色/状态由 ``GuiCore/styles.py`` 的 ``#CTextarea_PlainTextEdit`` 提供，
    圆角、内边距、字号由本类本地覆盖。
    """

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        rows: int = 3,
        size: str = "md",
        auto_resize: bool = True,
        max_height: int = 240,
        corners: tuple[bool, bool, bool, bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CTextarea_PlainTextEdit")
        self._size = size
        self._auto_resize = auto_resize
        self._max_height = max_height
        self._corners = corners
        self._rows = rows

        spec = size_spec(size)
        self._min_height = spec.padding_x * 2 + rows * self.fontMetrics().lineSpacing()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_geometry()

        if text:
            self.setPlainText(text)
        if placeholder:
            self.setPlaceholderText(placeholder)
        if auto_resize:
            self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)
            self._adjust_height()

    def _apply_geometry(self) -> None:
        spec = size_spec(self._size)
        self.setStyleSheet(
            f"#CTextarea_PlainTextEdit {{ {corner_css(RADIUS, self._corners)}"
            f" padding: {max(4, spec.padding_x - 4)}px {spec.padding_x}px;"
            f" font-size: {spec.font_px}px; }}"
        )
        self.setFixedHeight(self._min_height)

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        self._corners = corners
        self._apply_geometry()

    def set_size(self, size: str) -> None:
        self._size = size
        spec = size_spec(size)
        self._min_height = spec.padding_x * 2 + self._rows * self.fontMetrics().lineSpacing()
        self._apply_geometry()

    def _adjust_height(self, *_args) -> None:
        if not self._auto_resize:
            return
        height = int(self.document().size().height()) + 2 * self.frameWidth() + 10
        self.setFixedHeight(max(self._min_height, min(self._max_height, height)))


__all__ = ["CTextarea"]
