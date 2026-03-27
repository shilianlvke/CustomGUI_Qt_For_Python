import sys

from AppCore import (
    Logger,
    ColorPalette,
    Language,
    PathFactory,
    AppSettings,
    AppThemes,
    AppLanguages,
    initialize_app_context,
    record_event,
)
from GUI import UiMainWindow, SetupMainWindow, MainFunctions
from GUI.windows.main_window.controller import MainWindowController
from qt_core import QApplication, QMainWindow, QIcon


class MainWindow(QMainWindow):
    """应用主窗口。

    负责：
    1. 启动期 UI 初始化与主题/语言装载；
    2. 将按钮事件转发给主窗口控制器；
    3. 处理窗口级事件（缩放、鼠标按下）。
    """

    def __init__(self, **args):
        """初始化主窗口并完成启动期装配。

        参数:
        - **args: 预留扩展参数。

        返回:
        - None
        """

        super().__init__()
        # 启动遥测：主窗口初始化
        record_event("app.main_window.init", category="app")
        self.setObjectName("CustomUI")
        # 允许窗口追踪鼠标移动
        self.setMouseTracking(True)

        # 启动阶段加载主题与语言资源
        Logger.debug(f"窗口主题：{AppSettings.theme_name}")
        Logger.debug(f"语言包：{AppSettings.language}")
        ColorPalette.update(AppThemes[AppSettings.theme_name].data)
        Language.update(AppLanguages[AppSettings.language].data)

        # 设置初始尺寸与最小尺寸
        Logger.debug(f"窗口大小：{AppSettings.startup_size}")
        self.resize(AppSettings.startup_size[0], AppSettings.startup_size[1])
        self.setMinimumSize(AppSettings.minimum_size[0], AppSettings.minimum_size[1])

        # 初始化 UI 并完成主窗口装配
        self.ui = UiMainWindow()
        self.ui.setup_ui(self)
        SetupMainWindow.setup_gui(self)

        # 控制器负责按钮路由、页面切换与交互编排
        self.controller = MainWindowController(self)

        # 展示窗口并记录就绪事件
        self.show()
        record_event("app.main_window.ready", category="app")

    def btn_clicked(self):
        """处理按钮点击并分发到控制器。

        返回:
        - None
        """

        # 统一从 UI 层取 sender，再交给控制器分发
        btn = SetupMainWindow.setup_btns(self)
        if btn is None:
            return
        self.controller.handle_button(btn)

    def btn_released(self):
        """处理按钮释放事件。

        返回:
        - None
        """

        SetupMainWindow.setup_btns(self)

    def resizeEvent(self, event):
        """处理窗口缩放并更新夹点位置。

        参数:
        - event: 缩放事件对象。

        返回:
        - None
        """

        SetupMainWindow.resize_grips(self)

    def mousePressEvent(self, event):
        """处理鼠标按下并记录拖拽起点。

        参数:
        - event: 鼠标事件对象。

        返回:
        - None
        """

        self.dragPos = event.globalPosition().toPoint()
        # 点击窗口其他区域时转移焦点
        self.focusNextChild()


if __name__ == "__main__":
    # 启动前初始化全局应用上下文（配置、主题、语言等）
    initialize_app_context()

    # 创建 Qt 应用对象
    app = QApplication(sys.argv)

    # app.setQuitOnLastWindowClosed(False)
    # # 创建托盘图标
    # tray_icon = QSystemTrayIcon()
    # tray_icon.setIcon(QIcon(PathFactory.set_jpg_image("托盘")))  # 设置托盘图标
    # tray_icon.setToolTip("CustomUI Open Source")  # 设置提示信息
    # menu = QMenu()
    # show_action = QAction("显示主界面")
    # quit_action = QAction("退出")
    # # 绑定菜单事件
    # show_action.triggered.connect(
    #     lambda: MainWindow(
    #         sys_settings=sys_settings,
    #         sys_config=loading_window.loader.sys_config,
    #     )
    # )
    # quit_action.triggered.connect(app.quit)
    # menu.addAction(show_action)
    # menu.addAction(quit_action)
    # tray_icon.setContextMenu(menu)  # 设置右键菜单
    # # 显示托盘图标
    # tray_icon.setVisible(True)

    # 应用级样式和图标
    app.setStyle("windows11")
    app.setWindowIcon(QIcon(PathFactory.set_ico(AppSettings.logo)))

    # 创建主窗口并进入事件循环
    MainWindow()
    sys.exit(app.exec())
