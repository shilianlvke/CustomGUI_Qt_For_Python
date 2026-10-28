from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QWidget
from AppCore import Language


class CCredits(QWidget):
    def __init__(self):
        super().__init__()
        # PROPERTIES
        self._copyright = Language.custom_ui.sys_copyright
        self._version = Language.custom_ui.sys_version

        # SETUP UI
        self.setup_ui()
        Language.subscribe(self.apply_language)

    def apply_language(self):
        """清空旧语言残留并刷新版权和版本文本。"""
        self._copyright = Language.custom_ui.sys_copyright
        self._version = Language.custom_ui.sys_version
        self.copyright_label.setText(self._copyright)
        self.version_label.setText(self._version)

    def setup_ui(self):
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
