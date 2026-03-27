from qt_core import QFrame, QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, Qt, QWidget
from AppCore import Language


class CCredits(QWidget):
    """底部版权信息栏组件。"""

    def __init__(self):
        """初始化版权信息栏。

        返回:
        - None
        """

        super().__init__()
        # PROPERTIES
        self._copyright = Language.custom_ui.sys_copyright
        self._version = Language.custom_ui.sys_version

        # SETUP UI
        self.setup_ui()

    def setup_ui(self):
        """构建版权信息栏布局。

        返回:
        - None
        """

        # ADD LAYOUT
        self.widget_layout = QHBoxLayout(self)
        self.widget_layout.setContentsMargins(0, 0, 0, 0)

        # BG FRAME
        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("CCredits_Bg_Frame")

        # ADD TO LAYOUT
        self.widget_layout.addWidget(self.bg_frame)

        # ADD BG LAYOUT
        self.bg_layout = QHBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)

        # ADD COPYRIGHT TEXT
        self.copyright_label = QLabel(self._copyright)
        self.copyright_label.setAlignment(Qt.AlignVCenter)

        # ADD VERSION TEXT
        self.version_label = QLabel(self._version)
        self.version_label.setAlignment(Qt.AlignVCenter)

        # SEPARATOR
        self.separator = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ADD TO LAYOUT
        self.bg_layout.addWidget(self.copyright_label)
        self.bg_layout.addSpacerItem(self.separator)
        self.bg_layout.addWidget(self.version_label)
