from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel

from AppCore import get_design_tokens


class CToolTip(QLabel):
    """提示气泡。

    样式约定（与 ``CPushButton`` 一致）：**颜色与字体**由 ``GuiCore/styles.py``
    的 ``#label_tooltip`` 提供，强调边方向经动态属性 ``accent`` 选择；本类只声明
    objectName / accent，并本地提供**实例级几何**（圆角、内边距）。

    ``accent`` 取 ``left`` / ``top`` / ``right``，分别对应左列按钮、标题栏按钮、
    左列关闭按钮三处调用。半径与内边距默认回落到设计令牌，显式传参即可覆盖。

    本类替代了原先分散在三处按钮文件里的 ``_ToolTip`` 私有实现（三者除强调边
    方向外完全相同）。
    """

    def __init__(
        self,
        parent,
        tooltip,
        accent="left",
        radius=None,
        padding=None,
        minimum_height=34,
    ):
        super().__init__()
        tokens = get_design_tokens()
        self.accent = accent
        self.radius = tokens.radius.tooltip if radius is None else radius
        self.padding = tokens.spacing.padding_md if padding is None else padding

        # LABEL SETUP
        self.setObjectName("label_tooltip")
        # 动态属性必须先于样式表设置：QSS 属性选择器在 polish 时求值
        self.setProperty("accent", accent)
        self._apply_geometry()
        self.setMinimumHeight(minimum_height)
        self.setParent(parent)
        self.setText(tooltip)
        self.adjustSize()

        # SET DROP SHADOW
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(30)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(0)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)

    def _apply_geometry(self):
        """实例级几何：圆角与左右内边距（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(
            f"#label_tooltip {{"
            f" border-radius: {self.radius}px;"
            f" padding-left: {self.padding}px;"
            f" padding-right: {self.padding}px; }}"
        )
