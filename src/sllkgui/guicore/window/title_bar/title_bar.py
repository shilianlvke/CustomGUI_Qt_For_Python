from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, ColorPalette, Language, PathFactory
from sllkgui.guicore.custom_ui.div import CVDiv

from ...acrylic import acrylic_active, glass_tint
from .title_button import CTitleButton

#: 非亚克力模式下留给窗口外阴影的边距（最大化时归零）。
#: 保留为兼容别名，运行时以 :attr:`AppSettings.title_bar_margin` 为准。
_CUSTOM_MARGINS = (10, 10, 10, 10)


def fit_logo_size(svg: QSvgWidget, limit: int) -> QSize:
    """把 SVG 控件固定为 ``limit`` 范围内的等比尺寸。

    ``QSvgWidget`` 会把图稿直接拉伸填满控件矩形，不做等比缩放；而标题栏的
    logo 容器宽度固定为 ``icon_size``、高度跟随标题栏，两者不相等时方形图标
    就会被横向压扁。这里按 SVG 自身的宽高比算出目标尺寸并固定，非方形图标
    （如 2:1 的横幅）同样不会被拉变形。
    """
    limit = max(1, int(limit))
    renderer = svg.renderer()
    natural = renderer.defaultSize() if renderer is not None else QSize()
    if natural.isValid() and natural.width() > 0 and natural.height() > 0:
        size = natural.scaled(limit, limit, Qt.KeepAspectRatio)
    else:
        size = QSize(limit, limit)
    svg.setFixedSize(size)
    return size


class CTitleBar(QWidget):
    # SIGNALS
    clicked = Signal(object)
    released = Signal(object)

    def __init__(self, parent, app_parent):
        super().__init__()
        self._parent = parent
        self._app_parent = app_parent
        self.settings = AppSettings
        #: 非亚克力模式下窗口外圈留白（配置值，最大化时归零）
        self._custom_margin = int(AppSettings.title_bar_margin)

        # 最大化状态跟随窗口实例（此前是模块级全局，多窗口会互相串状态）
        self._is_maximized = False
        self._old_size = QSize()

        # 参数
        self._logo_image = AppSettings.logo_title
        self._dark_one = ColorPalette.custom_dark_one
        # 标题栏在玻璃模式下是半透明面板，按钮常态必须透明才能透出亚克力底
        self._bg_color = glass_tint(ColorPalette.custom_dark_three, 0.0)
        self._div_color = ColorPalette.custom_bg_three
        self._btn_bg_color = glass_tint(ColorPalette.custom_dark_three, 0.0)
        self._btn_bg_color_hover = ColorPalette.custom_bg_three
        self._btn_bg_color_pressed = ColorPalette.custom_bg_one
        self._context_color = ColorPalette.custom_context_color
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._icon_color_active = ColorPalette.custom_icon_active
        self._font_family = AppSettings.family
        self._title_size = AppSettings.title_size
        self._text_foreground = ColorPalette.custom_text_foreground
        self._is_custom_title_bar = AppSettings.custom_title_bar
        self.minimize_btn = Language.UI.ui_Minimize
        self.maximize_btn = Language.UI.ui_Maximize
        self.close_btn = Language.UI.ui_Close
        # 自定义菜单按钮注册表：btn_id -> 按钮；语言键映射：btn_id -> tooltip_key
        self._custom_buttons: dict = {}
        self._custom_lang_keys: dict = {}
        self.setup_ui()

        # 语言切换时自动刷新提示文本（弱引用订阅）
        Language.subscribe(self.apply_language)

        # 设置logo宽度
        self.top_logo.setMinimumWidth(AppSettings.icon_size)
        self.top_logo.setMaximumWidth(AppSettings.icon_size)

        # self.top_logo.setPixmap(Functions.set_svg_image(logo_image))

        # 拖动锚点：按下时光标与窗口左上角在全局坐标下的偏移量。
        # 为 None 表示本次按下没有落在标题栏的可拖动区域（例如按在标题栏按钮
        # 上），此时收到移动事件也不搬动窗口。锚点由 CTitleBar 自己维护，
        # 宿主窗口不需要预先定义 dragPos 之类的属性。
        self._drag_offset = None

        # 移动应用程序小部件。
        # 除原有的 logo / 标题 / 分割线外，还要覆盖标题栏底板（bg）与标题栏
        # 自身：它们都是主界面 CWindow 的子控件，事件留在原控件树上，不需要
        # 任何额外的背景窗口；空白区域同样可以拖动窗口。
        if self._is_custom_title_bar:
            draggable = (self, self.bg, self.top_logo, self.logo_svg, self.div_1, self.title_label, self.div_2, self.div_3)
            for widget in draggable:
                widget.mousePressEvent = self._drag_press
                widget.mouseMoveEvent = self._drag_move
                widget.mouseReleaseEvent = self._drag_release
                widget.mouseDoubleClickEvent = self.maximize_restore

        # 将小部件添加到标题栏
        # ///////////////////////////////////////////////////////////////
        self.bg_layout.addWidget(self.top_logo)
        self.bg_layout.addWidget(self.div_1)
        self.bg_layout.addWidget(self.title_label)
        self.bg_layout.addWidget(self.div_2)

        # 添加按钮按钮
        # ///////////////////////////////////////////////////////////////
        # Functions
        self.minimize_button.released.connect(lambda: parent.showMinimized())
        self.maximize_restore_button.released.connect(lambda: self.maximize_restore())
        self.close_button.released.connect(lambda: parent.close())

        # 额外BTN布局
        self.bg_layout.addLayout(self.custom_buttons_layout)

        # 添加按钮
        if self._is_custom_title_bar:
            self.bg_layout.addWidget(self.minimize_button)
            self.bg_layout.addWidget(self.maximize_restore_button)
            self.bg_layout.addWidget(self.close_button)

    # 在标题栏中添加按钮
    # 添加btns并发出信号
    # ///////////////////////////////////////////////////////////////
    @staticmethod
    def _resolve_text(value):
        """解析 ``language.*`` 资源键；普通字符串原样返回。"""
        return Language.resolve_key(value) if isinstance(value, str) else value

    def add_menus(self, parameters):
        if parameters is not None and len(parameters) > 0:
            for parameter in parameters:
                _btn_icon = PathFactory.resolve_svg(parameter["btn_icon"])
                _btn_id = parameter["btn_id"]
                _btn_tooltip_key = parameter["btn_tooltip"]
                _is_active = parameter["is_active"]

                self.menu = CTitleButton(
                    self._parent,
                    self._app_parent,
                    btn_id=_btn_id,
                    tooltip_text=self._resolve_text(_btn_tooltip_key),
                    bg_color=self._bg_color,
                    icon_color=self._icon_color,
                    icon_path=_btn_icon,
                    is_active=_is_active,
                )
                self.menu.clicked.connect(self.btn_clicked)
                self.menu.released.connect(self.btn_released)
                self._custom_buttons[_btn_id] = self.menu
                self._custom_lang_keys[_btn_id] = _btn_tooltip_key

                # ADD TO LAYOUT
                self.custom_buttons_layout.addWidget(self.menu)

            # ADD DIV
            if self._is_custom_title_bar:
                self.custom_buttons_layout.addWidget(self.div_3)

    def apply_language(self, resolver=None):
        """语言切换后刷新窗口控制按钮与自定义菜单按钮的提示文本（订阅自动触发）。"""
        resolver = resolver or self._resolve_text
        self.minimize_button.set_tooltip(resolver("language.UI.ui_Minimize"))
        maximize_key = "language.UI.ui_Restore" if self._is_maximized else "language.UI.ui_Maximize"
        self.maximize_restore_button.set_tooltip(resolver(maximize_key))
        self.close_button.set_tooltip(resolver("language.UI.ui_Close"))
        for btn_id, tooltip_key in self._custom_lang_keys.items():
            button = self._custom_buttons.get(btn_id)
            if button is not None:
                button.set_tooltip(resolver(tooltip_key))

    # 标题栏菜单发出信号
    def btn_clicked(self):
        sender = self.sender()
        self.clicked.emit(sender if sender is not None else self.menu)

    def btn_released(self):
        sender = self.sender()
        self.released.emit(sender if sender is not None else self.menu)

    # 设置标题栏文本
    # ///////////////////////////////////////////////////////////////
    def set_title(self, title):
        self.title_label.setText(title)

    # 窗口拖动
    # ///////////////////////////////////////////////////////////////
    def _drag_press(self, event):
        """标题栏按下：记录锚点并接管本次鼠标事件。

        按在标题栏按钮上时事件由按钮自己处理，不会走到这里；后续移动自然
        也不会移动窗口，避免「点按钮顺手一拖，窗口跟着飞出去」。
        """
        if event.button() != Qt.LeftButton or self._parent is None:
            return
        self._drag_offset = event.globalPosition().toPoint() - self._parent.pos()
        event.accept()

    def _drag_move(self, event):
        """按锚点平滑移动窗口（没有锚点的移动事件一律忽略）。"""
        if self._drag_offset is None:
            return
        if not (event.buttons() & Qt.LeftButton):
            # 松开按键时清掉锚点，防止下一次非标题栏拖动命中过期锚点
            self._drag_offset = None
            return
        if self._parent is None:
            return
        global_pos = event.globalPosition().toPoint()
        if self._parent.isMaximized():
            self._restore_for_drag(global_pos)
        else:
            self._parent.move(global_pos - self._drag_offset)
        event.accept()

    def _drag_release(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = None

    def _restore_for_drag(self, global_pos):
        """最大化状态下开始拖动：还原窗口，并让光标保持在标题栏的同一点。"""
        local = self.mapFromGlobal(global_pos)
        ratio = local.x() / max(1, self.width())
        parent = self._parent
        self.maximize_restore()
        normal = parent.normalGeometry()
        width = normal.width() if normal.width() > 0 else parent.width()
        parent.move(
            global_pos.x() - int(width * max(0.0, min(1.0, ratio))),
            global_pos.y() - local.y(),
        )
        self._drag_offset = global_pos - parent.pos()

    # 最大化/恢复
    # 最大化并恢复父窗口
    # ///////////////////////////////////////////////////////////////
    def maximize_restore(self, e=None):
        """最大化 / 还原父窗口。

        顺序很关键：**先把框架切到目标状态（只改动态属性，微秒级），再让窗口改尺寸**。
        旧实现是 ``showMaximized()`` 之后重建整张样式表，一次切换会让整棵控件树
        重新 polish（400+ 次 StyleChange、同步阻塞数十到数百毫秒），
        于是「点一下卡一下、还原再卡一下」。
        """
        parent = self._parent
        if parent is None:
            return

        maximize = not bool(parent.isMaximized())
        if maximize:
            self._old_size = QSize(parent.width(), parent.height())
        self._is_maximized = maximize

        self._apply_window_chrome(maximize)

        if maximize:
            parent.showMaximized()
        else:
            parent.showNormal()

    def _apply_window_chrome(self, maximized: bool) -> None:
        """按最大化状态刷新窗口框架、阴影、边距与按钮图标（全部为轻量操作）。"""
        ui = getattr(self._parent, "ui", None)
        if ui is not None:
            # 最大化/亚克力模式都铺满；只有"非亚克力 + 正常尺寸"才留阴影外圈
            margins = (0, 0, 0, 0) if (maximized or acrylic_active()) else (self._custom_margin,) * 4
            ui.central_widget_layout.setContentsMargins(*margins)
            window = getattr(ui, "window", None)
            if window is not None:
                if maximized:
                    window.set_stylesheet(border_radius=0, border_size=0)
                else:
                    window.set_stylesheet()
                set_shadow = getattr(window, "set_shadow_enabled", None)
                if callable(set_shadow):
                    set_shadow(not maximized)

        icon = "icon_restore" if maximized else "icon_maximize"
        self.maximize_restore_button.set_icon(PathFactory.set_svg_icon(icon))
        tooltip = "language.UI.ui_Restore" if maximized else "language.UI.ui_Maximize"
        self.maximize_restore_button.set_tooltip(self._resolve_text(tooltip))

    # SETUP APP
    # ///////////////////////////////////////////////////////////////
    def setup_ui(self):
        # ADD MENU LAYOUT
        self.title_bar_layout = QVBoxLayout(self)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)

        # ADD BG
        self.bg = QFrame()
        self.bg.setObjectName("CTitleBar_Bg_Frame")

        # ADD BG LAYOUT
        self.bg_layout = QHBoxLayout(self.bg)
        self.bg_layout.setContentsMargins(10, 0, 5, 0)
        self.bg_layout.setSpacing(0)

        # DIVS
        self.div_1 = CVDiv()
        self.div_2 = CVDiv()
        self.div_3 = CVDiv()

        # LEFT FRAME WITH MOVE APP
        self.top_logo = QLabel()
        self.top_logo_layout = QVBoxLayout(self.top_logo)
        self.top_logo_layout.setContentsMargins(0, 0, 0, 0)
        self.logo_svg = QSvgWidget()
        self.logo_svg.load(PathFactory.set_svg_image(self._logo_image))
        fit_logo_size(self.logo_svg, AppSettings.icon_size)
        self.top_logo_layout.addWidget(self.logo_svg, Qt.AlignCenter, Qt.AlignCenter)

        # TITLE LABEL（字号/字体由 sllkgui.guicore/styles.py 的 #CTitleBar_Title_Label 提供）
        self.title_label = QLabel()
        self.title_label.setObjectName("CTitleBar_Title_Label")
        self.title_label.setAlignment(Qt.AlignVCenter)

        # CUSTOM BUTTONS LAYOUT
        self.custom_buttons_layout = QHBoxLayout()
        self.custom_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_buttons_layout.setSpacing(0)

        # MINIMIZE BUTTON
        self.minimize_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.minimize_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_minimize"),
        )

        # MAXIMIZE / RESTORE BUTTON
        self.maximize_restore_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.maximize_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_maximize"),
        )

        # CLOSE BUTTON
        self.close_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.close_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_close"),
        )

        # ADD TO LAYOUT
        self.title_bar_layout.addWidget(self.bg)
