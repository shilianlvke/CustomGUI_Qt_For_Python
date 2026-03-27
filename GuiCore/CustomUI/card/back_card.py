"""模块说明。"""

from qt_core import QFrame, QSize


class CCard(QFrame):
    """卡片容器组件。"""

    def __init__(self, size: QSize = None) -> None:
        """初始化卡片组件。

        参数:
        - size: 可选固定尺寸。

        返回:
        - None
        """
        super().__init__()
        self.setObjectName("CCard_Frame")
        if size is not None:
            self.setFixedSize(size)
