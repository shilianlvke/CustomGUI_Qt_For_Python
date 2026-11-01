"""旧版通用按钮：保留构造签名，实现已收敛到 :class:`CButton`。"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from .button import CButton


class CPushButton(CButton):
    """兼容壳：``size`` 显式给出时按固定尺寸布局，其余行为与 ``CButton`` 一致。"""

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text: str | None = None,
        icon: QIcon | str | None = None,
        is_trans: bool = False,
    ):
        super().__init__(
            text=text or "",
            icon=icon,
            variant="text" if is_trans else "solid",
        )
        if size is not None:
            self.setFixedSize(size)


__all__ = ["CPushButton"]
