"""旧版单行输入框：保留构造签名，实现已收敛到 :class:`CInputText`。"""

from .input_text import CInputText


class CLineEdit(CInputText):
    """兼容壳：沿用 ``height=32`` 的旧视觉，其余行为与 ``CInputText`` 一致。"""

    def __init__(self, text="", place_holder_text="", parent=None):
        super().__init__(text=text, placeholder=place_holder_text, size="sm", parent=parent)


__all__ = ["CLineEdit"]
