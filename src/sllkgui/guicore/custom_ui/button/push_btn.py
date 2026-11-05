"""旧版通用按钮：保留构造签名，实现已收敛到 :class:`CButton`。"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from .button import CButton

#: 默认按钮尺寸；放进模块常量，避免在参数默认值里构造可变对象
_DEFAULT_SIZE = QSize(64, 32)


class CPushButton(CButton):
    """兼容壳：``size`` 显式给出时按固定尺寸布局，其余行为与 ``CButton`` 一致。"""

    def __init__(
        self,
        size: QSize = _DEFAULT_SIZE,
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
