"""窗口装配门面：宿主应用只需要认这一个模块。

``customgui.guis`` 是内部装配层，随时可能重组；对外稳定的是这里的名字：

- 窗口骨架：:class:`UiMainWindow` / :class:`SetupMainWindow` / :class:`MainWindowController`
- 应用插件：:func:`load_apps` / :func:`load_app_handles` / :class:`AppHandle`
- 语言切换：:func:`apply_language` / :func:`current_language` / :func:`available_languages`

最小宿主示例::

    import customgui
    from PySide6.QtWidgets import QApplication, QMainWindow
    from customgui.appcore import AppSettings, AppThemes, ColorPalette, Language
    from customgui.window import MainWindowController, SetupMainWindow, UiMainWindow

    customgui.configure(apps_dir="./apps", data_dir="./data")
    app = QApplication([])
    customgui.appcore.get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppSettings.language)

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.ui = UiMainWindow()
            self.ui.setup_ui(self)
            SetupMainWindow.setup_gui(self)
            self.controller = MainWindowController(self)
            self.show()
"""

from __future__ import annotations

from .guis import (
    MainFunctions,
    SetupMainWindow,
    Ui_LeftColumn,
    Ui_MainPages,
    Ui_RightColumn,
    UiMainWindow,
)
from .guis.app_loader import (
    AppContext,
    AppHandle,
    discover_app_dirs,
    get_app_handle,
    load_app_handles,
    load_app_manifest,
    load_apps,
    register_app,
    reset_apps_cache,
)
from .guis.language_service import apply_language, available_languages, current_language
from .guis.windows.main_window.controller import MainWindowController

__all__ = [
    # 窗口骨架
    "UiMainWindow",
    "SetupMainWindow",
    "MainWindowController",
    "MainFunctions",
    "Ui_MainPages",
    "Ui_LeftColumn",
    "Ui_RightColumn",
    # 应用插件
    "AppContext",
    "AppHandle",
    "discover_app_dirs",
    "get_app_handle",
    "load_app_handles",
    "load_app_manifest",
    "load_apps",
    "register_app",
    "reset_apps_cache",
    # 语言
    "apply_language",
    "available_languages",
    "current_language",
]
