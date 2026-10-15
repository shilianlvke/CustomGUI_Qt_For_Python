import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from AppCore import (
    AppError,
    AppLanguages,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    Logger,
    PathFactory,
    get_app_context,
    record_event,
    track_timing,
)
from Guis import SetupMainWindow, UiMainWindow
from Guis.windows.main_window.controller import MainWindowController


class MainWindow(QMainWindow):
    """应用主窗口。

    负责：
    1. 启动期 UI 初始化与主题/语言装载；
    2. 将按钮事件转发给主窗口控制器；
    3. 处理窗口级事件（缩放、鼠标按下）。
    """

    def __init__(self, **args):
        super().__init__()
        # 启动遥测：主窗口初始化
        record_event("app.main_window.init", category="app")
        self.setObjectName("CustomUI")
        # 允许窗口追踪鼠标移动
        self.setMouseTracking(True)

        # 设置初始尺寸与最小尺寸
        Logger.debug(f"当前窗口大小：{AppSettings.startup_size}")
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
        # 统一从 UI 层取 sender，再交给控制器分发
        btn = SetupMainWindow.setup_btns(self)
        if btn is None:
            return
        self.controller.handle_button(btn)

    def btn_released(self):
        SetupMainWindow.setup_btns(self)

    def resizeEvent(self, event):
        SetupMainWindow.resize_grips(self)

    def mousePressEvent(self, event):
        self.dragPos = event.globalPosition().toPoint()
        # 点击窗口其他区域时转移焦点
        self.focusNextChild()


if __name__ == "__main__":
    try:
        # 启动前初始化全局应用上下文（配置、主题、语言等），并接入计时与遥测
        with track_timing("app.config_load", category="perf"):
            get_app_context()
        record_event(
            "app.config_loaded",
            category="app",
            payload={"theme": AppSettings.theme_name, "language": AppSettings.language},
        )
        # 启动阶段加载主题与语言资源
        Logger.debug(f"当前窗口主题：{AppSettings.theme_name}")
        Logger.debug(f"当前语言包：{AppSettings.language}")
        ColorPalette.update(AppThemes[AppSettings.theme_name].data)
        Language.update(AppLanguages[AppSettings.language].data)
        # 创建 Qt 应用对象
        app = QApplication(sys.argv)

        # 应用级样式和图标
        app.setStyle("windows11")
        app.setWindowIcon(QIcon(PathFactory.set_ico(AppSettings.logo)))

        # 创建主窗口并进入事件循环
        MainWindow()
        sys.exit(app.exec())
    except AppError as exc:
        Logger.error(str(exc))
        record_event(
            "app.startup_error",
            category="app",
            level="error",
            payload={"code": exc.code, "layer": exc.layer, "details": exc.details},
        )
        sys.exit(1)
    except Exception as exc:
        Logger.exception(f"应用启动失败: {exc}")
        record_event(
            "app.startup_error",
            category="app",
            level="error",
            payload={"error": str(exc)},
        )
        sys.exit(1)
