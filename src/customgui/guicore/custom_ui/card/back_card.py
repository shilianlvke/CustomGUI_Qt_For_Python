from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame


class CCard(QFrame):
    def __init__(self, size: QSize = None):
        super().__init__()
        self.setObjectName("CCard_Frame")
        if size is not None:
            self.setFixedSize(size)
