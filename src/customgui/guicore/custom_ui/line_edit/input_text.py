"""单行输入框（复刻 PrimeVue Aura InputText）。"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QLineEdit, QSizePolicy

from customgui.appcore import PathFactory

from ..icon_utils import render_icon
from .input_style import colors, corner_css, icon_gap, radius, size_spec


class CInputText(QLineEdit):
    """Aura 风格单行输入框。

    颜色/状态（normal / hover / focus / invalid / disabled）由 ``customgui.guicore/styles.py``
    的 ``#CInputText_LineEdit`` 提供；高度、圆角、内边距、字号属几何量，由本类本地
    覆盖（与 ``CPushButton`` 的约定一致）。
    """

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        size: str = "md",
        invalid: bool = False,
        icon: str | QIcon | None = None,
        icon_pos: str = "left",
        fluid: bool = True,
        corners: tuple[bool, bool, bool, bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CInputText_LineEdit")
        self._size = size
        self._invalid = False
        self._icon_pos = icon_pos
        self._icon_action = None
        self._icon_source: str | None = None
        self._icon_object: QIcon | None = None
        self._corners = corners

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding if fluid else QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._apply_geometry()

        if text:
            self.setText(text)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.set_invalid(invalid)
        if icon is not None:
            self.set_icon(icon, icon_pos)

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    def _leading_icon(self) -> bool:
        return self._icon_action is not None and self._icon_pos == "left"

    def _trailing_icon(self) -> bool:
        return self._icon_action is not None and self._icon_pos == "right"

    def _apply_geometry(self) -> None:
        spec = size_spec(self._size)
        left = spec.padding_x + (spec.icon_px + icon_gap() if self._leading_icon() else 0)
        right = spec.padding_x + (spec.icon_px + icon_gap() if self._trailing_icon() else 0)
        self.setFixedHeight(spec.height)
        self.setStyleSheet(
            f"#CInputText_LineEdit {{ height: {spec.height}px; {corner_css(radius(), self._corners)}"
            f" padding-left: {left}px; padding-right: {right}px; font-size: {spec.font_px}px; }}"
        )

    def set_size(self, size: str) -> None:
        self._size = size
        self._apply_geometry()

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        """按 (左上, 右上, 右下, 左下) 指定圆角，供输入框组拼接使用。"""
        self._corners = corners
        self._apply_geometry()

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def set_invalid(self, invalid: bool) -> None:
        self._invalid = bool(invalid)
        self.setProperty("invalid", "true" if invalid else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def is_invalid(self) -> bool:
        return self._invalid

    # ------------------------------------------------------------------
    # 图标
    # ------------------------------------------------------------------
    def set_icon(self, icon: str | QIcon | None, icon_pos: str | None = None) -> None:
        if self._icon_action is not None:
            self.removeAction(self._icon_action)
            self._icon_action = None
        self._icon_source = icon if isinstance(icon, str) else None
        self._icon_object = icon if isinstance(icon, QIcon) else None
        if icon is None:
            self._apply_geometry()
            return

        if icon_pos is not None:
            self._icon_pos = icon_pos
        position = (
            QLineEdit.ActionPosition.LeadingPosition
            if self._icon_pos == "left"
            else QLineEdit.ActionPosition.TrailingPosition
        )
        self._icon_action = self.addAction(self._tinted_icon(), position)
        self._apply_geometry()

    def _tinted_icon(self) -> QIcon:
        """按当前主题的 ``form.field.icon.color`` 给图标着色。

        图标 SVG 自带写死的强调色填充，直接交给 ``QIcon`` 会永远是那个蓝色，
        既跟不上主题也跟 disabled/invalid 状态无关，所以统一走 render_icon 着色。
        """
        if self._icon_source is None:
            return self._icon_object or QIcon()
        pixmap = render_icon(
            self._icon_source,
            QColor(colors()["icon"]),
            size_spec(self._size).icon_px,
            self.devicePixelRatioF(),
        )
        if pixmap is None:
            return QIcon(PathFactory.set_svg_icon(self._icon_source))
        return QIcon(pixmap)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        # 主题切换会重建应用样式表 → 图标要跟着重新着色
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            if self._icon_action is not None:
                self._icon_action.setIcon(self._tinted_icon())


__all__ = ["CInputText"]
