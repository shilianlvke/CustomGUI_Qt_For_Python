"""模块说明。"""

################################################################################
## Form generated from reading UI file 'right_column.ui'
##
## Created by: Qt User Interface Compiler version 6.4.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QMetaObject,
    Qt,
)
from PySide6.QtGui import (
    QFont,
)
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget


class UiRightColumn:
    """右侧列 UI 生成类。"""

    def setup_ui(self, right_column: QWidget) -> None:
        """构建右侧列界面。"""
        if not right_column.objectName():
            right_column.setObjectName("RightColumn")
        right_column.resize(240, 600)
        self.main_pages_layout = QVBoxLayout(right_column)
        self.main_pages_layout.setSpacing(0)
        self.main_pages_layout.setObjectName("main_pages_layout")
        self.main_pages_layout.setContentsMargins(5, 5, 5, 5)
        self.menus = QStackedWidget(right_column)
        self.menus.setObjectName("menus")
        self.menu_1 = QWidget()
        self.menu_1.setObjectName("menu_1")
        self.verticalLayout = QVBoxLayout(self.menu_1)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(5, 5, 5, 5)
        self.label_1 = QLabel(self.menu_1)
        self.label_1.setObjectName("label_1")
        font = QFont()
        font.setPointSize(16)
        self.label_1.setFont(font)
        self.label_1.setStyleSheet("font-size: 16pt")
        self.label_1.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.label_1)

        self.menus.addWidget(self.menu_1)
        self.menu_2 = QWidget()
        self.menu_2.setObjectName("menu_2")
        self.verticalLayout_2 = QVBoxLayout(self.menu_2)
        self.verticalLayout_2.setSpacing(5)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(5, 5, 5, 5)
        self.label_2 = QLabel(self.menu_2)
        self.label_2.setObjectName("label_2")
        self.label_2.setFont(font)
        self.label_2.setStyleSheet("font-size: 16pt")
        self.label_2.setAlignment(Qt.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_2)

        self.menus.addWidget(self.menu_2)

        self.main_pages_layout.addWidget(self.menus)

        self.retranslate_ui(right_column)

        self.menus.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(right_column)

    # setup_ui

    def retranslate_ui(self, right_column: QWidget) -> None:
        """刷新界面文本。"""
        right_column.setWindowTitle(QCoreApplication.translate("RightColumn", "Form", None))
        self.label_1.setText(QCoreApplication.translate("RightColumn", "Menu 1 - Right Menu", None))
        self.label_2.setText(QCoreApplication.translate("RightColumn", "Menu 2 - Right Menu", None))

    # retranslate_ui
