"""头像组（复刻 PrimeVue AvatarGroup：横向重叠 + 溢出计数）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .avatar import CAvatar, _resolve_size
from .palette import content_surface_color, tokens


class _OverflowBubble(QWidget):
    """``+N`` 溢出头像。"""

    def __init__(self, count: int, size: int, parent=None):
        super().__init__(parent)
        self._count = max(1, int(count))
        self.setFixedSize(size, size)

    def count(self) -> int:
        return self._count

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.setBrush(content_surface_color())
        painter.drawEllipse(rect)
        font = QFont(self.font())
        font.setPixelSize(max(11, int(self.width() * 0.34)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette["text"]))
        painter.drawText(rect, Qt.AlignCenter, f"+{self._count}")
        painter.end()


class CAvatarGroup(QWidget):
    """横向重叠头像组；超过 ``max_count`` 时用 ``+N`` 兜底。"""

    def __init__(
        self,
        avatars=None,
        max_count: int | None = None,
        overlap: int = 10,
        size: str | int = "md",
        parent=None,
    ):
        super().__init__(parent)
        self._sources: list = list(avatars or [])
        self._max_count = None if max_count is None else max(1, int(max_count))
        self._overlap = max(0, int(overlap))
        self._avatar_size = _resolve_size(size)
        self._avatars: list[CAvatar] = []
        self._overflow: _OverflowBubble | None = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._rebuild()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def avatars(self) -> list[CAvatar]:
        return list(self._avatars)

    def visible_avatar_count(self) -> int:
        return len(self._avatars)

    def overflow_count(self) -> int:
        if self._overflow is None:
            return 0
        return self._overflow.count()

    def total_count(self) -> int:
        return len(self._sources)

    def max_count(self) -> int | None:
        return self._max_count

    def set_max_count(self, count: int | None) -> None:
        self._max_count = None if count is None else max(1, int(count))
        self._rebuild()

    def overlap(self) -> int:
        return self._overlap

    def set_overlap(self, overlap: int) -> None:
        self._overlap = max(0, int(overlap))
        self._sync_geometry()

    def avatar_size(self) -> int:
        return self._avatar_size

    def set_size(self, size: str | int) -> None:
        self._avatar_size = _resolve_size(size)
        for avatar in self._avatars:
            avatar.set_size(self._avatar_size)
        if self._overflow is not None:
            self._overflow.setFixedSize(self._avatar_size, self._avatar_size)
        self._sync_geometry()

    def set_avatars(self, avatars) -> None:
        self._sources = list(avatars or [])
        self._rebuild()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _clear(self) -> None:
        for avatar in self._avatars:
            avatar.hide()
            avatar.setParent(None)
            avatar.deleteLater()
        self._avatars = []
        if self._overflow is not None:
            self._overflow.hide()
            self._overflow.setParent(None)
            self._overflow.deleteLater()
            self._overflow = None

    def _show_count(self) -> tuple[int, int]:
        """返回 (展示头像数, 溢出数)。"""
        total = len(self._sources)
        if self._max_count is not None and total > self._max_count:
            visible = self._max_count - 1
            return visible, total - visible
        return total, 0

    def _rebuild(self) -> None:
        self._clear()
        visible, overflow = self._show_count()
        for source in self._sources[:visible]:
            avatar = self._make_avatar(source)
            avatar.setParent(self)
            avatar.set_size(self._avatar_size)
            avatar.show()
            self._avatars.append(avatar)
        if overflow > 0:
            self._overflow = _OverflowBubble(overflow, self._avatar_size, self)
            self._overflow.show()
        self._sync_geometry()
        self.update()

    def _make_avatar(self, source) -> CAvatar:
        if isinstance(source, CAvatar):
            return source
        if isinstance(source, dict):
            return CAvatar(
                label=str(source.get("label", "")),
                icon=source.get("icon"),
                image=source.get("image"),
                size=self._avatar_size,
            )
        return CAvatar(label=str(source), size=self._avatar_size)

    def _sync_geometry(self) -> None:
        step = max(1, self._avatar_size - self._overlap)
        x = 0
        for avatar in self._avatars:
            avatar.move(x, 0)
            avatar.raise_()
            x += step
        if self._overflow is not None:
            self._overflow.move(x, 0)
            self._overflow.raise_()
        slots = len(self._avatars) + (1 if self._overflow is not None else 0)
        width = self._avatar_size + (slots - 1) * step if slots else 0
        self.setFixedSize(width, self._avatar_size)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self.width(), self._avatar_size)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self.sizeHint()

    # ------------------------------------------------------------------
    # 绘制（头像之间的分隔环）
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(tokens()["border"]), 2))
        painter.setBrush(Qt.NoBrush)
        radius = self._avatar_size / 2 + 1
        step = max(1, self._avatar_size - self._overlap)
        for index in range(len(self._avatars) + (1 if self._overflow is not None else 0)):
            center_x = index * step + self._avatar_size / 2
            painter.drawEllipse(
                QRectF(center_x - radius, self._avatar_size / 2 - radius, radius * 2, radius * 2)
            )
        painter.end()


__all__ = ["CAvatarGroup"]
