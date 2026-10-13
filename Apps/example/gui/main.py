"""示例应用（Apps/example）：展示应用模组协议的最简形态。

约定：gui/main.py 导出 ``build_page(app) -> QWidget``，
基座会自动把返回的控件挂载为页面（app 为 AppContext，
可用 ``app.lang_text("key")`` 读取本应用语言、``app.config`` 读取清单）。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings
from GuiCore import CCard


def build_page(app):
    """构建应用页面：返回 QWidget，基座负责挂载。"""
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "examplePage")

    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    card = CCard()
    card_layout = QVBoxLayout(card)
    card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title = QLabel(app.lang_text("app_text"))
    title.setStyleSheet(f'font: 700 20pt "{AppSettings.family}";')
    card_layout.addWidget(title)

    tooltip = QLabel(app.lang_text("app_tooltip"))
    card_layout.addWidget(tooltip)

    layout.addWidget(card)
    return page
