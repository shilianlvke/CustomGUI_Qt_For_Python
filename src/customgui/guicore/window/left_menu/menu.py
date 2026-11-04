from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, ColorPalette, Language, PathFactory, get_design_tokens
from customgui.guicore.custom_ui.div import CHDiv

from .menu_button import CLeftMenuButton
from .overlay import menu_panel_width, menu_rail_width


class CLeftMenu(QWidget):
    # 信号
    clicked = Signal(object)
    released = Signal(object)

    def __init__(
        self, parent=None, app_parent=None, radius=None, icon_path="icon_menu", icon_path_close="icon_menu_close"
    ):
        super().__init__()
        self.setObjectName("CLeftMenu_QWidget")
        self.parent = parent
        self.app_parent = app_parent
        self._dark_one = ColorPalette.custom_dark_one
        self._dark_three = ColorPalette.custom_dark_three
        self._dark_four = ColorPalette.custom_dark_four
        self._bg_one = ColorPalette.custom_bg_one
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._icon_color_active = ColorPalette.custom_icon_active
        self._context_color = ColorPalette.custom_context_color
        self._text_foreground = ColorPalette.custom_text_foreground
        self._text_active = ColorPalette.custom_text_active
        self._duration_time = AppSettings.time_animation
        # 圆角为实例级几何：未显式传入时回落到设计令牌
        self._radius = get_design_tokens().radius.window if radius is None else radius
        self._minimum_width = AppSettings.lef_menu_size.minimum
        self._maximum_width = AppSettings.lef_menu_size.maximum
        self._icon_path = PathFactory.set_svg_icon(icon_path)
        self._icon_path_close = PathFactory.set_svg_icon(icon_path_close)
        self._font_family = AppSettings.family
        # 菜单按钮注册表：btn_id -> 按钮；语言键映射：btn_id -> (text_key, tooltip_key)
        self._menu_buttons: dict = {}
        self._menu_lang_keys: dict = {}
        # 获取父类
        self._parent = parent
        self._app_parent = app_parent

        # 绘制UI
        self.setup_ui()

        # 语言切换时自动刷新菜单文本（弱引用订阅）
        Language.subscribe(self.apply_language)

        # 切换按钮和DIV菜单
        self.toggle_button = CLeftMenuButton(
            app_parent,
            text=Language.UI.ui_Hide,
            tooltip_text=Language.UI.ui_Show,
            icon_path=icon_path,
            minimum_width=self._minimum_width,
            maximum_width=self._maximum_width,
            font_family=self._font_family,
        )
        self.toggle_button.clicked.connect(self.toggle_animation)
        self.div_top = CHDiv()

        # 将展开按钮和分割线添加到顶部布局
        self.top_layout.addWidget(self.toggle_button)
        self.top_layout.addWidget(self.div_top)  # 分割线

        # 将分割线添加到底部布局
        self.div_bottom = CHDiv()
        self.div_bottom.hide()
        self.bottom_layout.addWidget(self.div_bottom)

    # 为左侧菜单添加按钮
    # 添加按钮并设置信号
    # ///////////////////////////////////////////////////////////////
    @staticmethod
    def _resolve_text(value, fallback=None):
        """解析 ``language.*`` 资源键；普通字符串原样返回。

        缺语言资源时回退到 ``fallback``（应用名），不再把原始 key 直接显示
        在菜单里——那会被省略号截成 ``language.app.xxx.ap`` 这样的乱码。
        """
        if not isinstance(value, str):
            return value
        text = Language.resolve_key(value, fallback)
        if text == value and fallback:
            return fallback
        return text

    def add_menus(self, parameters):
        if parameters is not None:
            for parameter in parameters:
                _btn_icon = PathFactory.resolve_svg(parameter["btn_icon"])
                _btn_id = parameter["btn_id"]
                _btn_text_key = parameter["btn_text"]
                _btn_tooltip_key = parameter["btn_tooltip"]
                _btn_fallback = parameter.get("btn_text_fallback")
                _show_top = parameter["show_top"]
                _is_active = parameter["is_active"]

                self.menu = CLeftMenuButton(
                    self._app_parent,
                    text=self._resolve_text(_btn_text_key, _btn_fallback),
                    btn_id=_btn_id,
                    tooltip_text=self._resolve_text(_btn_tooltip_key, _btn_fallback),
                    icon_path=_btn_icon,
                    is_active=_is_active,
                    font_family=self._font_family,
                )
                self.menu.clicked.connect(self.btn_clicked)
                self.menu.released.connect(self.btn_released)
                self._menu_buttons[_btn_id] = self.menu
                self._menu_lang_keys[_btn_id] = (_btn_text_key, _btn_tooltip_key, _btn_fallback)

                # 添加到布局
                if _show_top:
                    self.top_layout.addWidget(self.menu)
                else:
                    self.div_bottom.show()
                    self.bottom_layout.addWidget(self.menu)

    def apply_language(self, resolver=None):
        """语言切换后刷新全部菜单按钮文本与提示（订阅自动触发）。"""
        resolver = resolver or self._resolve_text
        self.toggle_button.setText(resolver("language.UI.ui_Hide"))
        self.toggle_button.set_tooltip(resolver("language.UI.ui_Show"))
        for btn_id, (text_key, tooltip_key, fallback) in self._menu_lang_keys.items():
            button = self._menu_buttons.get(btn_id)
            if button is None:
                continue
            button.setText(resolver(text_key, fallback))
            button.set_tooltip(resolver(tooltip_key, fallback))

    def active_button_id(self):
        """返回当前激活的菜单按钮 ID（无激活按钮时返回 None）。"""
        for btn_id, button in self._menu_buttons.items():
            if button.is_active():
                return btn_id
        return None

    # 左侧菜单发射信号
    def btn_clicked(self):
        sender = self.sender()
        self.clicked.emit(sender if sender is not None else self.menu)
        # Overlay 下点完菜单项立即收回到轨道，避免浮层持续盖住新页面
        if getattr(self._parent.window(), "_menu_mode", "static") == "overlay" and self._overlay_expanded():
            self.collapse()

    def btn_released(self):
        sender = self.sender()
        self.released.emit(sender if sender is not None else self.menu)

    # 展开/缩回左菜单
    def toggle_animation(self):
        if self._parent is None:
            return
        if self.is_expanded():
            self.collapse()
        else:
            self.expand()

    def is_expanded(self) -> bool:
        """当前是否处于展开态（按两种宽度取中值判定，兼容内容边距）。"""
        if self._parent is None:
            return False
        threshold = (menu_rail_width() + menu_panel_width()) // 2
        return self._parent.width() > threshold

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        """设置展开态；``animate=False`` 时立即到位（启动初始化用）。"""
        target = menu_panel_width() if expanded else menu_rail_width()
        if animate:
            self._animate_width(target, expanded)
            return
        if self._parent is None:
            return
        overlay = getattr(self._parent.window(), "_menu_mode", "static") == "overlay"
        if overlay:
            rect = self._parent.geometry()
            self._parent.setGeometry(QRect(rect.x(), rect.y(), max(1, int(target)), rect.height()))
        else:
            self._parent.setMinimumWidth(target)
            self._parent.setMaximumWidth(target)
        self.sync_toggle_appearance(expanded)
        self._sync_overlay_scrim()

    def _animate_width(self, target: int, expanded: bool) -> None:
        if self._parent is None:
            return
        window = self._parent.window()
        overlay = getattr(window, "_menu_mode", "static") == "overlay"
        duration = self._duration_time
        easing = QEasingCurve(QEasingCurve.Type.InOutCubic)
        if overlay:
            # Overlay：菜单框已脱离布局、浮在内容区之上，只能对 geometry 做动画
            # （改 minimumWidth 不会带动实际宽度）；更短的时长与 OutCubic 更跟手。
            start = self._parent.geometry()
            end = QRect(start.x(), start.y(), max(1, int(target)), start.height())
            self.animation = QPropertyAnimation(self._parent, b"geometry")
            self.animation.setStartValue(start)
            self.animation.setEndValue(end)
            duration = self._overlay_duration()
            easing = QEasingCurve(QEasingCurve.Type.OutCubic)
            if expanded:
                self._show_overlay_scrim()
        else:
            # Static：菜单框是布局成员，宽度由 minimumWidth 决定；但窗口初始会把
            # maximumWidth 钉在收起宽度上，只动画 minimumWidth 会被立刻夹回，
            # 因此两条约束必须同步动画，否则展开无效或中途回弹。
            current_min = self._parent.minimumWidth()
            current_max = self._parent.maximumWidth()
            group = QParallelAnimationGroup(self._parent)
            for prop, start_value in ((b"minimumWidth", current_min), (b"maximumWidth", current_max)):
                anim = QPropertyAnimation(self._parent, prop, group)
                anim.setStartValue(start_value)
                anim.setEndValue(target)
                group.addAnimation(anim)
            self.animation = group
            self._animation_children = [anim]
        self.animation.stop()
        self.sync_toggle_appearance(expanded)
        if overlay:
            self.animation.setEasingCurve(easing)
            self.animation.setDuration(duration)
        else:
            # QParallelAnimationGroup 没有时长/曲线设置，需逐个子动画配置。
            for anim in self._animation_children:
                anim.setEasingCurve(easing)
                anim.setDuration(duration)
        self.animation.finished.connect(self._sync_overlay_scrim)
        self.animation.start()

    def sync_toggle_appearance(self, expanded: bool) -> None:
        """同步展开按钮的 active 与图标（不触发动画，供宿主切换模式时调用）。"""
        self.toggle_button.set_active_toggle(bool(expanded))
        self.toggle_button.set_icon(self._icon_path_close if expanded else self._icon_path)

    def set_overlay_appearance(self, enabled: bool) -> None:
        """Overlay 浮层使用接近不透明的面板底色，避免与页面文字互相穿透。

        只在 ``bg`` 上打一个动态属性，由全局样式表的属性选择器接管颜色；
        切换模式时重刷该控件，不重建样式表。
        """
        self.bg.setProperty("overlay", "true" if enabled else None)
        style = self.bg.style()
        style.unpolish(self.bg)
        style.polish(self.bg)
        self.bg.update()

    def _overlay_duration(self) -> int:
        """Overlay 展开/收起时长：与右侧抽屉共用一组配置，收起更迅速。"""
        try:
            return int(AppSettings.overlay.drawer_duration)
        except Exception:
            return 200

    def _show_overlay_scrim(self) -> None:
        window = self._parent.window()
        scrim = getattr(window, "_menu_overlay_scrim", None)
        if scrim is None:
            return
        scrim.fade_in()
        scrim.raise_()
        self._parent.raise_()

    def _sync_overlay_scrim(self) -> None:
        """动画结束后按实际宽度显示/淡出遮罩（收起才淡出，展开保持可见）。"""
        parent = self._parent
        if parent is None:
            return
        window = parent.window()
        if getattr(window, "_menu_mode", "static") != "overlay":
            return
        scrim = getattr(window, "_menu_overlay_scrim", None)
        if scrim is None:
            return
        if self.is_expanded():
            scrim.fade_in()
            scrim.raise_()
            parent.raise_()
        else:
            scrim.fade_out()

    def _overlay_expanded(self) -> bool:
        return self.is_expanded()

    def expand(self) -> None:
        self._animate_width(menu_panel_width(), True)

    def collapse(self) -> None:
        self._animate_width(menu_rail_width(), False)

    # 仅选择一个BTN
    def select_only_one(self, widget: str):
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == widget:
                btn.set_active(True)
            else:
                btn.set_active(False)

    # 仅选择一个选项卡BTN
    def select_only_one_tab(self, widget: str):
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == widget:
                btn.set_active_tab(True)
            else:
                btn.set_active_tab(False)

    # 取消选择所有BTN
    def deselect_all(self):
        for btn in self.findChildren(QPushButton):
            btn.set_active(False)

    # 取消选择所有标签
    def deselect_all_tab(self):
        for btn in self.findChildren(QPushButton):
            btn.set_active_tab(False)

    # SETUP APP
    # ///////////////////////////////////////////////////////////////
    def setup_ui(self):
        # 添加菜单布局
        self.left_menu_layout = QVBoxLayout(self)
        self.left_menu_layout.setContentsMargins(0, 0, 0, 0)

        # 添加背景框架（配色见 customgui.guicore/styles.py；圆角是实例参数，本地覆盖）
        self.bg = QFrame()
        self.bg.setObjectName("CLeftMenu_Bg_Frame")
        self.bg.setStyleSheet(f"#CLeftMenu_Bg_Frame {{ border-radius: {self._radius}px; }}")

        # 添加顶部框架
        self.top_frame = QFrame()
        self.top_frame.setObjectName("CLeftMenu_top_Frame")

        # 添加底部框架
        self.bottom_frame = QFrame()
        self.bottom_frame.setObjectName("CLeftMenu_bottom_Frame")

        # 添加背景布局
        self._layout = QVBoxLayout(self.bg)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # 添加顶部布局
        self.top_layout = QVBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(1)

        # 添加底部布局
        self.bottom_layout = QVBoxLayout(self.bottom_frame)
        self.bottom_layout.setContentsMargins(0, 0, 0, 8)
        self.bottom_layout.setSpacing(1)

        # 将顶部框架、底部框架添加到背景布局
        self._layout.addWidget(self.top_frame, 0, Qt.AlignTop)
        self._layout.addWidget(self.bottom_frame, 0, Qt.AlignBottom)

        # 添加背景到菜单布局
        self.left_menu_layout.addWidget(self.bg)
