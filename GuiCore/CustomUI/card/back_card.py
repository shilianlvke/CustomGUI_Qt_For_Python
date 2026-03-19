from qt_core import QFrame, QSize


class CCard(QFrame):

    def __init__(self, size: QSize = None):
        super().__init__()
        self.setObjectName("CCard_Frame")
        if size is not None:
            self.setFixedSize(size)
