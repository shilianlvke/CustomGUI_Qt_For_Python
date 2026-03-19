from qt_core import QLabel, QPixmap, QVBoxLayout, Qt, QWidget


# PY ICON WITH CUSTOM COLORS
# ///////////////////////////////////////////////////////////////
class CPixmap(QWidget):
    def __init__(self, pic_path):
        super().__init__()
        # PROPERTIES
        self._icon_path = pic_path

        # SETUP UI
        self.setup_ui()

    def setup_ui(self):
        # LAYOUT
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # LABEL
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # PAINTER
        self.set_icon(self._icon_path)

        # ADD TO LAYOUT
        self.layout.addWidget(self.icon)

    def set_icon(self, icon_path):
        # # GET COLOR
        # color = ""
        # if icon_color is not None:
        #     color = icon_color
        # else:
        #     color = self._icon_color
        #
        # # PAINTER / PIXMAP
        icon = QPixmap(icon_path)
        # icon.scaled()
        # painter = QPainter(icon)
        # painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        # painter.fillRect(icon.rect(), color)
        # painter.end()

        # SET PIXMAP
        self.icon.setPixmap(icon)
