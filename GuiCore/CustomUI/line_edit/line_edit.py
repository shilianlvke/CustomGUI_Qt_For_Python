from qt_core import QLineEdit


# PY PUSH BUTTON
# ///////////////////////////////////////////////////////////////
class CLineEdit(QLineEdit):
    def __init__(self, text="", place_holder_text=""):
        super().__init__()
        self.setObjectName("CLineEdit_LineEdit")

        # PARAMETERS
        if text:
            self.setText(text)
        if place_holder_text:
            self.setPlaceholderText(place_holder_text)
