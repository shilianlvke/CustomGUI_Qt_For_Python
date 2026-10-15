from PySide6.QtWidgets import QLineEdit

from AppCore import get_design_tokens


# PY PUSH BUTTON
# ///////////////////////////////////////////////////////////////
class CLineEdit(QLineEdit):
    """单行输入框。

    样式约定（与 ``CPushButton`` 一致）：颜色与状态由 ``GuiCore/styles.py`` 的
    ``#CLineEdit_LineEdit`` 提供；固定高度属组件几何，由本类本地覆盖并取设计
    令牌 ``size.control_height``。
    """

    def __init__(self, text="", place_holder_text=""):
        super().__init__()
        self.setObjectName("CLineEdit_LineEdit")
        self._apply_geometry()

        # PARAMETERS
        if text:
            self.setText(text)
        if place_holder_text:
            self.setPlaceholderText(place_holder_text)

    def _apply_geometry(self):
        """实例级几何：固定高度（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(f"#CLineEdit_LineEdit {{ height: {get_design_tokens().size.control_height}px; }}")
