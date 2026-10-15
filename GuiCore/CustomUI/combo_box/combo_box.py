from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QComboBox

# 下拉箭头区域宽度（与主题无关，故不进全局样式表）
_DROP_DOWN_WIDTH = 20


class CComboBox(QComboBox):
    """下拉选择框。

    样式约定（与 ``CPushButton`` 一致）：颜色与状态由 ``GuiCore/styles.py`` 的
    ``#CComboBox_ComboBox`` 提供；下拉箭头区域宽度属组件几何，由本类本地覆盖。
    """

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
        self._apply_geometry()
        # 设置占位符文本
        self.setEditable(is_editable)
        if placeholder_text:
            self.setPlaceholderText(placeholder_text)
        if items:
            self.addItems(items)
        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply_geometry(self):
        """实例级几何：下拉箭头区域宽度（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(f"#CComboBox_ComboBox::drop-down {{ width: {_DROP_DOWN_WIDTH}px; }}")
