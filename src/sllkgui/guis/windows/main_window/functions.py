import os

from PySide6 import QtCore, QtGui
from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsDropShadowEffect,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from sllkgui.appcore import AppSettings
from sllkgui.guicore import CPageTransition
from sllkgui.guicore.window.left_menu.overlay import (
    CLeftMenuOverlayTracker,
    CMenuOverlayScrim,
    menu_panel_width,
    menu_rail_width,
    overlay_menu_rect,
    overlay_scrim_rect,
)

from .drawers import DrawerLayout, normalize_drawer_mode


# FUNCTIONS
class MainFunctions:
    # SET MAIN WINDOW PAGES
    # ///////////////////////////////////////////////////////////////
    def set_page(self, page, animate=True, *, menu=None, button_id=None, previous_button_id=None):
        """切换内容区页面。

        ``animate=False`` 时瞬时切换（如语言重建页面）；
        ``menu`` / ``button_id`` / ``previous_button_id`` 让栏目按钮高亮跟随过场时序。

        过场以整张区域背景卡片（``content_area_left_frame``）为画布：卡片底色与
        圆角都进动画，页面内容与卡片表面是同一块画面，一起擦除、一起展开。
        """
        pages = self.ui.load_pages.pages
        if not animate:
            CPageTransition.cancel(pages)
            pages.setCurrentWidget(page)
            return
        CPageTransition.switch(
            pages,
            page,
            menu=menu,
            button_id=button_id,
            previous_button_id=previous_button_id,
            stage=getattr(self.ui, "content_area_left_frame", None),
        )

    # SET LEFT MENU MODE
    # ///////////////////////////////////////////////////////////////
    def set_menu_mode(self, mode):
        """切换左菜单模式：``static`` 布局内占位，``overlay`` 浮层覆盖内容区。

        - ``static``：菜单框是窗口水平布局的成员，展开时挤压内容区（默认）；
        - ``overlay``：布局里只保留一条与收起态等宽的轨道占位，菜单框浮在内容
          区之上；展开时覆盖内容、收起时回到轨道，内容区宽度始终不变。

        Overlay 额外提供：内容遮罩（点击/滚轮关闭并拦截穿透）、面板阴影、
        Esc 收起、点击菜单项后自动收起。切换模式不会重建菜单按钮，也不影响
        当前页面。
        """
        value = "overlay" if str(mode).lower() == "overlay" else "static"
        if getattr(self, "_menu_mode", "static") == value:
            return
        self._menu_mode = value
        if value == "overlay":
            MainFunctions._enter_overlay_menu(self)
        else:
            MainFunctions._exit_overlay_menu(self)

    @staticmethod
    def _enter_overlay_menu(window):
        """进入 Overlay：轨道占位 + 浮动菜单 + 遮罩 + 阴影 + Esc。"""
        ui = window.ui
        frame = ui.left_menu_frame
        layout = ui.window.layout
        thin = menu_rail_width()
        wide = menu_panel_width()

        # 轨道占位：收起态仍占住布局宽度，展开的浮层不会推动内容区
        spacer = getattr(ui, "_menu_overlay_spacer", None)
        if spacer is None:
            spacer = QWidget(ui.window)
            spacer.setObjectName("CMenuOverlaySpacer")
            spacer.setFixedWidth(thin)
            spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            layout.insertWidget(0, spacer)
            ui._menu_overlay_spacer = spacer

        if layout.indexOf(frame) >= 0:
            layout.removeWidget(frame)
        frame.setParent(ui.window)
        frame.setMinimumWidth(thin)
        frame.setMaximumWidth(wide)
        frame.setGeometry(overlay_menu_rect(window, thin))
        frame.show()

        # 面板阴影只作用于浮动菜单本身；不做整窗阴影，避免亚克力残影
        effect = QGraphicsDropShadowEffect(frame)
        effect.setBlurRadius(28)
        effect.setXOffset(0)
        effect.setYOffset(8)
        effect.setColor(QColor(0, 0, 0, 90))
        frame.setGraphicsEffect(effect)
        window._menu_overlay_shadow = effect

        scrim = CMenuOverlayScrim(ui.window)
        scrim.setGeometry(overlay_scrim_rect(window))
        scrim.dismissed.connect(ui.left_menu.collapse)
        window._menu_overlay_scrim = scrim

        tracker = CLeftMenuOverlayTracker(window)
        window.installEventFilter(tracker)
        window._menu_overlay_tracker = tracker

        shortcut = QShortcut(QKeySequence(Qt.Key_Escape), ui.window)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(ui.left_menu.collapse)
        window._menu_overlay_esc = shortcut

        ui.left_menu.sync_toggle_appearance(False)
        ui.left_menu.set_overlay_appearance(True)
        frame.raise_()

    @staticmethod
    def _exit_overlay_menu(window):
        """退出 Overlay：撤掉遮罩/阴影/快捷键/跟随器与轨道占位。"""
        ui = window.ui
        frame = ui.left_menu_frame
        layout = ui.window.layout

        scrim = getattr(window, "_menu_overlay_scrim", None)
        if scrim is not None:
            scrim.hide()
            scrim.deleteLater()
            window._menu_overlay_scrim = None

        tracker = getattr(window, "_menu_overlay_tracker", None)
        if tracker is not None:
            window.removeEventFilter(tracker)
            tracker.deleteLater()
            window._menu_overlay_tracker = None

        shortcut = getattr(window, "_menu_overlay_esc", None)
        if shortcut is not None:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
            window._menu_overlay_esc = None

        if frame.graphicsEffect() is not None:
            frame.setGraphicsEffect(None)
        window._menu_overlay_shadow = None

        spacer = getattr(ui, "_menu_overlay_spacer", None)
        if spacer is not None:
            layout.removeWidget(spacer)
            spacer.deleteLater()
            ui._menu_overlay_spacer = None

        thin = menu_rail_width()
        frame.setMinimumWidth(thin)
        frame.setMaximumWidth(thin)
        frame.setParent(ui.window)
        if layout.indexOf(frame) < 0:
            layout.insertWidget(0, frame)
        ui.left_menu.sync_toggle_appearance(False)
        ui.left_menu.set_overlay_appearance(False)
        frame.show()

    # SET DRAWER MODE
    # ///////////////////////////////////////////////////////////////
    def _drawers(self) -> DrawerLayout:
        """惰性创建四向抽屉布局策略（旧宿主/测试桩不会触发）。"""
        layout = getattr(self, "_drawer_layout", None)
        if layout is None:
            layout = DrawerLayout(self)
            self._drawer_layout = layout
        return layout

    def drawer_mode(self) -> str:
        return getattr(self, "_drawer_mode", "static")

    def set_drawer_mode(self, mode) -> None:
        """切换四向抽屉模式：``static`` 布局占位，``overlay`` 浮层覆盖。

        与 ``menu_mode`` 相互独立：后者只控制左侧图标菜单。运行期切换会保留
        当前已展开的抽屉（记录状态 → 换容器 → 恢复）。
        """
        value = normalize_drawer_mode(mode)
        drawer = MainFunctions._drawers(self)
        drawer.set_mode(value)
        self._drawer_mode = value

    def is_drawer_overlay(self) -> bool:
        return MainFunctions.drawer_mode(self) == "overlay"

    # SET LEFT COLUMN PAGES
    # ///////////////////////////////////////////////////////////////
    def set_left_column_menu(self, menu, title, icon_path):
        self.ui.left_column.menus.menus.setCurrentWidget(menu)
        # 走 set_title 而不是直接写 label：保留语言键，切换语言后标题才会刷新。
        self.ui.left_column.set_title(title)
        self.ui.left_column.icon.set_icon(icon_path)

    # RETURN IF LEFT COLUMN IS VISIBLE
    # ///////////////////////////////////////////////////////////////
    def left_column_is_visible(self):
        if MainFunctions.is_drawer_overlay(self):
            return MainFunctions._drawers(self).is_open("left")
        return self.ui.left_column_frame.width() != 0

    # RETURN IF RIGHT COLUMN IS VISIBLE
    # ///////////////////////////////////////////////////////////////
    def right_column_is_visible(self):
        if MainFunctions.is_drawer_overlay(self):
            return MainFunctions._drawers(self).right_is_open()
        return self.ui.right_column_frame.width() != 0

    # SET RIGHT COLUMN PAGES
    # ///////////////////////////////////////////////////////////////
    def set_right_column_menu(self, menu):
        self.ui.right_column.menus.setCurrentWidget(menu)

    # SET TOP / BOTTOM COLUMN PAGES
    # ///////////////////////////////////////////////////////////////
    def set_top_column_menu(self, menu, title, icon_path):
        self.ui.top_column.menus.menus.setCurrentWidget(menu)
        self.ui.top_column.title_label.setText(title)
        self.ui.top_column.icon.set_icon(icon_path)

    def set_bottom_column_menu(self, menu, title, icon_path):
        self.ui.bottom_column.menus.menus.setCurrentWidget(menu)
        self.ui.bottom_column.title_label.setText(title)
        self.ui.bottom_column.icon.set_icon(icon_path)

    # RETURN IF TOP / BOTTOM COLUMN IS VISIBLE
    # ///////////////////////////////////////////////////////////////
    def top_column_is_visible(self):
        if MainFunctions.is_drawer_overlay(self):
            return MainFunctions._drawers(self).is_open("top")
        return self.ui.top_column_frame.height() != 0

    def bottom_column_is_visible(self):
        if MainFunctions.is_drawer_overlay(self):
            return MainFunctions._drawers(self).is_open("bottom")
        return self.ui.bottom_column_frame.height() != 0

    # GET TITLE BUTTON BY OBJECT NAME
    # ///////////////////////////////////////////////////////////////
    def get_title_bar_btn(self, object_name):
        return self.ui.title_bar_frame.findChild(QPushButton, object_name)

    # GET TITLE BUTTON BY OBJECT NAME
    # ///////////////////////////////////////////////////////////////
    def get_left_menu_btn(self, object_name):
        return self.ui.left_menu.findChild(QPushButton, object_name)

    # LEDT AND RIGHT COLUMNS / SHOW / HIDE
    # ///////////////////////////////////////////////////////////////
    def toggle_left_column(self):
        if MainFunctions.is_drawer_overlay(self):
            MainFunctions._drawers(self).toggle("left")
            return
        # GET ACTUAL CLUMNS SIZE
        width = self.ui.left_column_frame.width()
        right_column_width = self.ui.right_column_frame.width()
        MainFunctions.start_box_animation(self, width, right_column_width, "left")

    def toggle_right_column(self):
        # GET ACTUAL CLUMNS SIZE
        left_column_width = self.ui.left_column_frame.width()
        width = self.ui.right_column_frame.width()
        MainFunctions.start_box_animation(self, left_column_width, width, "right")

    def toggle_top_column(self):
        if MainFunctions.is_drawer_overlay(self):
            drawer = MainFunctions._drawers(self)
            if drawer.is_open("top"):
                drawer.close("top")
            else:
                # 与 Static 一致：同一主轴只保留一个抽屉
                drawer.close("bottom", animate=False)
                drawer.open("top")
            return
        # GET ACTUAL COLUMNS SIZE
        top_column_height = self.ui.top_column_frame.height()
        bottom_column_height = self.ui.bottom_column_frame.height()
        MainFunctions.start_box_animation_vertical(self, top_column_height, bottom_column_height, "top")

    def toggle_bottom_column(self):
        if MainFunctions.is_drawer_overlay(self):
            drawer = MainFunctions._drawers(self)
            if drawer.is_open("bottom"):
                drawer.close("bottom")
            else:
                drawer.close("top", animate=False)
                drawer.open("bottom")
            return
        # GET ACTUAL COLUMNS SIZE
        top_column_height = self.ui.top_column_frame.height()
        bottom_column_height = self.ui.bottom_column_frame.height()
        MainFunctions.start_box_animation_vertical(self, top_column_height, bottom_column_height, "bottom")

    def start_box_animation(self, left_box_width, right_box_width, direction):
        time_animation = AppSettings.time_animation
        minimum_left = AppSettings.left_column_size.minimum
        maximum_left = AppSettings.left_column_size.maximum
        minimum_right = AppSettings.right_column_size.minimum
        maximum_right = AppSettings.right_column_size.maximum

        # Check Left Values
        if left_box_width <= minimum_left and direction == "left":
            left_width = maximum_left
        else:
            left_width = minimum_left

        # Check Right values
        if right_box_width <= minimum_right and direction == "right":
            right_width = maximum_right
        else:
            right_width = minimum_right

        # GROUP ANIMATION
        # min/max 成对动画：左右列初始 maximumWidth 为 0，只动 minimumWidth 会被
        # 上限夹住、抽屉根本打不开。开 = 两者都到 maximum，关 = 都回 minimum。
        self.group = QParallelAnimationGroup()
        self.group.stop()
        for frame, start, end in (
            (self.ui.left_column_frame, left_box_width, left_width),
            (self.ui.right_column_frame, right_box_width, right_width),
        ):
            for property_name in (b"minimumWidth", b"maximumWidth"):
                animation = QPropertyAnimation(frame, property_name)
                animation.setDuration(time_animation)
                animation.setStartValue(start)
                animation.setEndValue(end)
                animation.setEasingCurve(QEasingCurve.InOutQuart)
                self.group.addAnimation(animation)
        self.group.start()

    def start_box_animation_vertical(self, top_box_height, bottom_box_height, direction):
        """顶/底抽屉的开合动画：与 :meth:`start_box_animation` 同一套规则，主轴换成高度。

        与左右列的区别：``minimumHeight`` / ``maximumHeight`` 成对动画。若只抬高
        ``minimum`` 而把 ``maximum`` 留在 0，min>max 会让 QVBoxLayout 在竖向空间
        紧张时错位（子控件相互重叠）。
        """
        time_animation = AppSettings.time_animation
        minimum_top = AppSettings.top_column_size.minimum
        maximum_top = AppSettings.top_column_size.maximum
        minimum_bottom = AppSettings.bottom_column_size.minimum
        maximum_bottom = AppSettings.bottom_column_size.maximum

        # Check Top values
        if top_box_height <= minimum_top and direction == "top":
            top_height = maximum_top
        else:
            top_height = minimum_top

        # Check Bottom values
        if bottom_box_height <= minimum_bottom and direction == "bottom":
            bottom_height = maximum_bottom
        else:
            bottom_height = minimum_bottom

        # GROUP ANIMATION（min/max 成对：开 = 两者都到 maximum，关 = 都回 minimum）
        self.group = QParallelAnimationGroup()
        self.group.stop()
        for frame, start, end in (
            (self.ui.top_column_frame, top_box_height, top_height),
            (self.ui.bottom_column_frame, bottom_box_height, bottom_height),
        ):
            for property_name in (b"minimumHeight", b"maximumHeight"):
                animation = QPropertyAnimation(frame, property_name)
                animation.setDuration(time_animation)
                animation.setStartValue(start)
                animation.setEndValue(end)
                animation.setEasingCurve(QEasingCurve.InOutQuart)
                self.group.addAnimation(animation)
        self.group.start()

    def set_select_path(self, obj):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        obj.setText(folder_path)

    def set_select_file(self, obj):
        file_path, file_name = QFileDialog.getOpenFileName(self, "选择文件")
        obj.setText(file_path)

    def open_directory(self):
        if os.path.isdir(self.app1_line_edit.text()):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.app1_line_edit.text()))
