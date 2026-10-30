"""滚动区域组件：默认透明，可选显式背景色。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea

from AppCore import get_theme_manager


class CScrollArea(QScrollArea):
    """透明滚动区：背景交由上层容器呈现，可选显式背景色。

    - ``background`` 为 None（默认）时 viewport 与内容部件**完全透明**，
      透出 ``#CWindow_Frame`` 的主题底色（``surface_app``）。"无背景"正是
      应用级样式表激活后 ``QStyleSheetStyle`` polish 的目标状态，不会被
      重置——由此免去此前调色板方案在 repolish（首次显示、主题切换、最大
      化/还原触发的 ``app.setStyleSheet`` 重建）后回落为默认浅色的问题；
    - ``background`` 显式传色时，内容部件经**属性选择器 QSS** 着色（与
      ``CCard`` 同机制：颜色由样式表系统维护，repolish 后自动保持）。不用
      调色板——polish 会把无 QSS 规则控件的调色板重置为样式默认浅色；
    - 不用裸 QSS 规则着色：不带选择器的规则会级联到滚动区内所有子控件，
      覆盖按钮等组件自身的 ``:hover`` 背景（表现为只有边框变色）。属性
      选择器只命中被标记的内容部件，对卡片/按钮零影响；
    - 订阅主题切换做防御性刷新（透明态与显式色均幂等；组件销毁自动退订）。
    """

    #: 标记"内容部件使用显式背景色"的动态属性，供属性选择器命中
    BG_PROP = "cScrollAreaContentBg"

    def __init__(self, parent=None, background=None, object_name=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if object_name is not None:
            self.setObjectName(object_name)
        self._background = background
        self.update_style()
        get_theme_manager().subscribe(self.update_style)

    def update_style(self):
        """按背景配置刷新样式与 viewport/内容部件。

        透明（默认）：全部关闭自绘；显式背景色：样式表只含一条属性选择器
        规则，命中被 ``BG_PROP`` 标记的内容部件。
        """
        self.setStyleSheet("")
        self.setFrameShape(QFrame.Shape.NoFrame)
        # viewport 永不自绘：透明模式下透出上层容器；显式模式下整个滚动口
        # 被（widgetResizable 拉伸至不小于视口的）内容部件覆盖
        self.viewport().setAutoFillBackground(False)
        widget = self.widget()
        if widget is not None:
            self._refresh_widget(widget)
        if self._background is not None:
            color = self._background
            self.setStyleSheet(
                f'QWidget[{self.BG_PROP}="true"] {{ background-color: {color}; }}'
            )

    def _refresh_widget(self, widget) -> None:
        """按背景配置同步内容部件的属性标记与自绘开关。"""
        if self._background is None:
            if widget.property(self.BG_PROP) is not None:
                widget.setProperty(self.BG_PROP, None)
                self._repolish(widget)
        else:
            widget.setProperty(self.BG_PROP, True)
            self._repolish(widget)
        widget.setAutoFillBackground(False)

    @staticmethod
    def _repolish(widget) -> None:
        """动态属性变化后强制重新解析样式规则。"""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def setWidget(self, widget):
        """挂载内容部件并同步背景配置。

        ``setWidget`` 常晚于构造期的 ``update_style``，且 QScrollArea 内部
        会对内容部件强制开启自绘，这里统一按当前配置刷一次。
        """
        super().setWidget(widget)
        if widget is not None:
            self._refresh_widget(widget)

    def set_background(self, color):
        """设置背景色（传 None 表示透明，透出上层容器底色）。"""
        self._background = color
        self.update_style()
