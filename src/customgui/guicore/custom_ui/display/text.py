"""文本（排版层级统一入口）。

页面里大量"纯文字"如果直接用 ``QLabel``，字号/字重/可选中就会在各处各写一份，
既不符合"可视组件全部来自基座"的约定，也无法随设计令牌统一调整。``CText``
只承载文字语义（字号、字重、等宽、换行、可选中），颜色沿用全局样式，因此
主题切换无需额外处理。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

#: 字号档位（像素）
_SIZES = {
    "xs": 12,
    "sm": 13,
    "md": 14,
    "lg": 17,
    "xl": 24,
    "metric": 22,
}

_WEIGHTS = {
    "regular": QFont.Weight.Normal,
    "medium": QFont.Weight.Medium,
    "semibold": QFont.Weight.DemiBold,
    "bold": QFont.Weight.Bold,
}

_MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "monospace"]


class CText(QLabel):
    """排版文本组件：``size`` + ``weight`` + ``mono`` + ``wrap``。"""

    def __init__(
        self,
        text: str = "",
        size: str = "md",
        weight: str = "regular",
        mono: bool = False,
        wrap: bool = False,
        selectable: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(text, parent)
        self._size = size if size in _SIZES else "md"
        self._weight = weight if weight in _WEIGHTS else "regular"
        self._mono = bool(mono)
        self.setWordWrap(bool(wrap))
        self.setTextInteractionFlags(Qt.TextSelectableByMouse if selectable else Qt.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._apply_font()

    # ------------------------------------------------------------------
    # 排版
    # ------------------------------------------------------------------
    def _apply_font(self) -> None:
        font = QFont(self.font())
        font.setPixelSize(_SIZES[self._size])
        font.setWeight(_WEIGHTS[self._weight])
        if self._mono:
            font.setFamilies(_MONO_FAMILIES)
        self.setFont(font)

    def text_size(self) -> str:
        return self._size

    def set_size(self, size: str) -> None:
        self._size = size if size in _SIZES else "md"
        self._apply_font()
        self.updateGeometry()

    def weight(self) -> str:
        return self._weight

    def set_weight(self, weight: str) -> None:
        self._weight = weight if weight in _WEIGHTS else "regular"
        self._apply_font()
        self.updateGeometry()

    def is_mono(self) -> bool:
        return self._mono

    def set_mono(self, mono: bool) -> None:
        self._mono = bool(mono)
        self._apply_font()
        self.updateGeometry()

    def set_text(self, text: str) -> None:
        self.setText(text)


__all__ = ["CText"]
