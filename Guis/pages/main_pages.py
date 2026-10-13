# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_pages.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject)
from PySide6.QtWidgets import (QStackedWidget, QVBoxLayout,
    QWidget)

class Ui_MainPages(object):
    def setupUi(self, MainPages):
        if not MainPages.objectName():
            MainPages.setObjectName(u"MainPages")
        MainPages.resize(838, 517)
        self.Main_layout = QVBoxLayout(MainPages)
        self.Main_layout.setSpacing(0)
        self.Main_layout.setObjectName(u"Main_layout")
        self.Main_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(MainPages)
        self.pages.setObjectName(u"pages")
        self.Main_Page = QWidget()
        self.Main_Page.setObjectName(u"Main_Page")
        self.pages.addWidget(self.Main_Page)
        self.widget_show = QWidget()
        self.widget_show.setObjectName(u"widget_show")
        self.pages.addWidget(self.widget_show)

        self.Main_layout.addWidget(self.pages)


        self.retranslateUi(MainPages)

        QMetaObject.connectSlotsByName(MainPages)
    # setupUi

    def retranslateUi(self, MainPages):
        MainPages.setWindowTitle(QCoreApplication.translate("MainPages", u"Form", None))
    # retranslateUi

