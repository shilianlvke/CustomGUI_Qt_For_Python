from qt_core import QComboBox, QSize, Qt


class CComboBox(QComboBox):

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        placeholder_text: str = None,
        items: list = None,
        is_editable=False,
    ):
        super().__init__()
        self.setObjectName("CComboBox_ComboBox")
        self.setFixedSize(size)
        self.setMaxVisibleItems(3)
        self.view().setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 设置占位符文本
        self.setEditable(is_editable)
        if placeholder_text:
            self.setPlaceholderText(placeholder_text)
        if items:
            self.addItems(items)
        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)
