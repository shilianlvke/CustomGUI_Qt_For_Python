"""模块说明。"""

################################################################################
## Form generated from reading UI file 'left_column.ui'
##
## Created by: Qt User Interface Compiler version 6.4.3
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
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class UiLeftColumn:
    """左侧列 UI 生成类。"""

    def setup_ui(self, left_column: QWidget) -> None:
        """构建左侧列界面。"""
        if not left_column.objectName():
            left_column.setObjectName("LeftColumn")
        left_column.resize(288, 600)
        self.main_pages_layout = QVBoxLayout(left_column)
        self.main_pages_layout.setSpacing(0)
        self.main_pages_layout.setObjectName("main_pages_layout")
        self.main_pages_layout.setContentsMargins(0, 0, 0, 0)
        self.menus = QStackedWidget(left_column)
        self.menus.setObjectName("menus")
        self.menu_1 = QWidget()
        self.menu_1.setObjectName("menu_1")
        self.verticalLayout = QVBoxLayout(self.menu_1)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(5, 5, 5, 5)
        self.btn_1_widget = QWidget(self.menu_1)
        self.btn_1_widget.setObjectName("btn_1_widget")
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.btn_1_widget.sizePolicy().hasHeightForWidth())
        self.btn_1_widget.setSizePolicy(size_policy)
        self.btn_1_layout = QVBoxLayout(self.btn_1_widget)
        self.btn_1_layout.setSpacing(0)
        self.btn_1_layout.setObjectName("btn_1_layout")
        self.btn_1_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_1_widget)

        self.btn_2_widget = QWidget(self.menu_1)
        self.btn_2_widget.setObjectName("btn_2_widget")
        self.btn_2_widget.setMinimumSize(QSize(0, 40))
        self.btn_2_widget.setMaximumSize(QSize(16777215, 40))
        self.btn_2_layout = QVBoxLayout(self.btn_2_widget)
        self.btn_2_layout.setSpacing(0)
        self.btn_2_layout.setObjectName("btn_2_layout")
        self.btn_2_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_2_widget)

        self.btn_3_widget = QWidget(self.menu_1)
        self.btn_3_widget.setObjectName("btn_3_widget")
        self.btn_3_widget.setMinimumSize(QSize(0, 40))
        self.btn_3_layout = QVBoxLayout(self.btn_3_widget)
        self.btn_3_layout.setSpacing(0)
        self.btn_3_layout.setObjectName("btn_3_layout")
        self.btn_3_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_3_widget)

        self.menus.addWidget(self.menu_1)
        self.menu_2 = QWidget()
        self.menu_2.setObjectName("menu_2")
        self.verticalLayout_2 = QVBoxLayout(self.menu_2)
        self.verticalLayout_2.setSpacing(5)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.scrollArea = QScrollArea(self.menu_2)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.scrollArea.setFrameShape(QFrame.NoFrame)
        self.scrollArea.setLineWidth(0)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setWidgetResizable(True)
        self.left_column_info = QWidget()
        self.left_column_info.setObjectName("left_column_info")
        self.left_column_info.setGeometry(QRect(0, 0, 201, 77))
        self.verticalLayout_3 = QVBoxLayout(self.left_column_info)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.left_column_info)
        self.label_2.setObjectName("label_2")
        size_policy_1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        size_policy_1.setHorizontalStretch(0)
        size_policy_1.setVerticalStretch(0)
        size_policy_1.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(size_policy_1)
        self.label_2.setMaximumSize(QSize(16777215, 30))
        font = QFont()
        font.setPointSize(16)
        self.label_2.setFont(font)
        self.label_2.setStyleSheet("font-size: 16pt")

        self.verticalLayout_3.addWidget(self.label_2)

        self.label_3 = QLabel(self.left_column_info)
        self.label_3.setObjectName("label_3")
        font1 = QFont()
        font1.setPointSize(9)
        self.label_3.setFont(font1)
        self.label_3.setStyleSheet("font-size: 9pt")
        self.label_3.setWordWrap(True)

        self.verticalLayout_3.addWidget(self.label_3)

        self.scrollArea.setWidget(self.left_column_info)

        self.verticalLayout_2.addWidget(self.scrollArea)

        self.menus.addWidget(self.menu_2)

        self.main_pages_layout.addWidget(self.menus)

        self.retranslate_ui(left_column)

        self.menus.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(left_column)

    # setup_ui

    def retranslate_ui(self, left_column: QWidget) -> None:
        """刷新界面文本。"""
        left_column.setWindowTitle(QCoreApplication.translate("LeftColumn", "Form", None))
        self.label_2.setText(QCoreApplication.translate("LeftColumn", "Menu 2 - Left Menu", None))
        self.label_3.setText(
            QCoreApplication.translate(
                "LeftColumn",
                "This is just an example menu.\nAdd Qt Widgets or your custom widgets here.",
                None,
            ),
        )

    # retranslate_ui
