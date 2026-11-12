"""窗口装配门面：宿主应用只需要认这一个模块。

- 窗口骨架：:class:`UiMainWindow` / :class:`SetupMainWindow` / :class:`MainWindowController`
- Gallery：:class:`GalleryWindow` / :func:`load_gallery` / :func:`load_run`
- 插件 API：:class:`GalleryContext` / :class:`Plugin`
- 语言切换：:func:`apply_language` / :func:`current_language` / :func:`available_languages`

最小宿主示例::

    import sllkgui
    from PySide6.QtWidgets import QApplication
    from sllkgui.window import load_run

    sllkgui.configure(data_dir="./data")
    app = QApplication([])
    window = load_run()
    window.show()
"""

from __future__ import annotations

from .gallery.api import GalleryContext, Permission, Plugin
from .gallery.registry import GalleryRegistry
from .gallery.window import GalleryWindow, load_gallery, load_run
from .guis import (
    MainFunctions,
    SetupMainWindow,
    Ui_LeftColumn,
    Ui_MainPages,
    Ui_RightColumn,
    UiMainWindow,
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
    # Gallery
    "GalleryContext",
    "GalleryRegistry",
    "GalleryWindow",
    "Permission",
    "Plugin",
    "load_gallery",
    "load_run",
    # 语言
    "apply_language",
    "available_languages",
    "current_language",
]
