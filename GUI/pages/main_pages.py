"""模块说明。"""

################################################################################
## Form generated from reading UI file 'main_pages.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget


class UiMainPages:
    """主页面容器 UI 生成类。"""

    def setup_ui(self, main_pages: QWidget) -> None:
        """构建主页面容器界面。"""
        if not main_pages.objectName():
            main_pages.setObjectName("MainPages")
        main_pages.resize(838, 517)
        self.main_layout = QVBoxLayout(main_pages)
        self.main_layout.setSpacing(0)
        self.main_layout.setObjectName("Main_layout")
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(main_pages)
        self.pages.setObjectName("pages")
        self.main_page = QWidget()
        self.main_page.setObjectName("Main_Page")
        self.pages.addWidget(self.main_page)
        self.widget_show = QWidget()
        self.widget_show.setObjectName("widget_show")
        self.pages.addWidget(self.widget_show)

        self.main_layout.addWidget(self.pages)

        self.retranslate_ui(main_pages)

        QMetaObject.connectSlotsByName(main_pages)

    # setup_ui

    def retranslate_ui(self, main_pages: QWidget) -> None:
        """刷新界面文本。"""
        main_pages.setWindowTitle(QCoreApplication.translate("MainPages", "Form", None))

    # retranslate_ui
