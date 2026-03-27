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


class Ui_MainPages:
    """主页面容器 UI 生成类。"""

    def setupUi(self, MainPages: QWidget) -> None:
        """构建主页面容器界面。"""
        if not MainPages.objectName():
            MainPages.setObjectName("MainPages")
        MainPages.resize(838, 517)
        self.Main_layout = QVBoxLayout(MainPages)
        self.Main_layout.setSpacing(0)
        self.Main_layout.setObjectName("Main_layout")
        self.Main_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(MainPages)
        self.pages.setObjectName("pages")
        self.Main_Page = QWidget()
        self.Main_Page.setObjectName("Main_Page")
        self.pages.addWidget(self.Main_Page)
        self.widget_show = QWidget()
        self.widget_show.setObjectName("widget_show")
        self.pages.addWidget(self.widget_show)

        self.Main_layout.addWidget(self.pages)

        self.retranslateUi(MainPages)

        QMetaObject.connectSlotsByName(MainPages)

    # setupUi

    def retranslateUi(self, MainPages: QWidget) -> None:
        """刷新界面文本。"""
        MainPages.setWindowTitle(QCoreApplication.translate("MainPages", "Form", None))

    # retranslateUi
