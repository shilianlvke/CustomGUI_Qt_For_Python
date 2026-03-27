from qt_core import QLineEdit


# PY PUSH BUTTON
# ///////////////////////////////////////////////////////////////
class CLineEdit(QLineEdit):
    """自定义输入框组件。"""

    def __init__(self, text="", place_holder_text=""):
        """初始化输入框。

        参数:
        - text: 初始文本。
        - place_holder_text: 占位提示文本。

        返回:
        - None
        """

        super().__init__()
        self.setObjectName("CLineEdit_LineEdit")

        # PARAMETERS
        if text:
            self.setText(text)
        if place_holder_text:
            self.setPlaceholderText(place_holder_text)
