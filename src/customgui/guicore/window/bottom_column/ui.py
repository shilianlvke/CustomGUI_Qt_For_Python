
################################################################################
## Form generated from reading UI file 'bottom_column.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QMetaObject,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QFont,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_BottomColumn:
    def setupUi(self, BottomColumn):
        if not BottomColumn.objectName():
            BottomColumn.setObjectName("BottomColumn")
        BottomColumn.resize(600, 240)
        self.main_pages_layout = QVBoxLayout(BottomColumn)
        self.main_pages_layout.setSpacing(0)
        self.main_pages_layout.setObjectName("main_pages_layout")
        self.main_pages_layout.setContentsMargins(0, 0, 0, 0)
        self.menus = QStackedWidget(BottomColumn)
        self.menus.setObjectName("menus")
        self.menu_1 = QWidget()
        self.menu_1.setObjectName("menu_1")
        self.verticalLayout = QVBoxLayout(self.menu_1)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(5, 5, 5, 5)
        self.scrollArea = QScrollArea(self.menu_1)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.scrollArea.setFrameShape(QFrame.NoFrame)
        self.scrollArea.setLineWidth(0)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setWidgetResizable(True)
        self.bottom_column_info = QWidget()
        self.bottom_column_info.setObjectName("bottom_column_info")
        self.bottom_column_info.setGeometry(QRect(0, 0, 588, 228))
        self.horizontalLayout = QHBoxLayout(self.bottom_column_info)
        self.horizontalLayout.setSpacing(8)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.label_1 = QLabel(self.bottom_column_info)
        self.label_1.setObjectName("label_1")
        self.label_1.setMaximumSize(QSize(16777215, 30))
        font = QFont()
        font.setPointSize(16)
        self.label_1.setFont(font)
        self.label_1.setStyleSheet("font-size: 16pt")

        self.horizontalLayout.addWidget(self.label_1)

        self.label_2 = QLabel(self.bottom_column_info)
        self.label_2.setObjectName("label_2")
        font1 = QFont()
        font1.setPointSize(9)
        self.label_2.setFont(font1)
        self.label_2.setStyleSheet("font-size: 9pt")
        self.label_2.setWordWrap(True)

        self.horizontalLayout.addWidget(self.label_2)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.scrollArea.setWidget(self.bottom_column_info)

        self.verticalLayout.addWidget(self.scrollArea)

        self.menus.addWidget(self.menu_1)

        self.main_pages_layout.addWidget(self.menus)

        self.retranslateUi(BottomColumn)

        self.menus.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(BottomColumn)

    # setupUi

    def retranslateUi(self, BottomColumn):
        BottomColumn.setWindowTitle(QCoreApplication.translate("BottomColumn", "Form", None))
        self.label_1.setText(QCoreApplication.translate("BottomColumn", "Menu 1 - Bottom Column", None))
        self.label_2.setText(
            QCoreApplication.translate(
                "BottomColumn", "This is just an example menu.\nAdd Qt Widgets or your custom widgets here.", None
            )
        )

    # retranslateUi
