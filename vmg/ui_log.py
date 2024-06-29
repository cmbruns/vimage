# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'log.ui'
##
## Created by: Qt User Interface Compiler version 6.4.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QTextEdit, QVBoxLayout, QWidget)

from vmg.logging_text_edit import LoggingQTextEdit

class Ui_LogDialog(object):
    def setupUi(self, LogDialog):
        if not LogDialog.objectName():
            LogDialog.setObjectName(u"LogDialog")
        LogDialog.resize(589, 576)
        font = QFont()
        LogDialog.setFont(font)
        self.verticalLayout = QVBoxLayout(LogDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.text_edit = LoggingQTextEdit(LogDialog)
        self.text_edit.setObjectName(u"text_edit")
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setReadOnly(True)

        self.verticalLayout.addWidget(self.text_edit)

        self.widget = QWidget(LogDialog)
        self.widget.setObjectName(u"widget")
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label = QLabel(self.widget)
        self.label.setObjectName(u"label")

        self.horizontalLayout.addWidget(self.label)

        self.comboBox = QComboBox(self.widget)
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setInsertPolicy(QComboBox.NoInsert)

        self.horizontalLayout.addWidget(self.comboBox)

        self.horizontalSpacer = QSpacerItem(360, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.saveLogButton = QPushButton(self.widget)
        self.saveLogButton.setObjectName(u"saveLogButton")

        self.horizontalLayout.addWidget(self.saveLogButton)


        self.verticalLayout.addWidget(self.widget)

#if QT_CONFIG(shortcut)
        self.label.setBuddy(self.comboBox)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(LogDialog)

        QMetaObject.connectSlotsByName(LogDialog)
    # setupUi

    def retranslateUi(self, LogDialog):
        LogDialog.setWindowTitle(QCoreApplication.translate("LogDialog", u"vimage log", None))
        self.label.setText(QCoreApplication.translate("LogDialog", u"Minimum Log Level:", None))
        self.comboBox.setItemText(0, QCoreApplication.translate("LogDialog", u"Critical", None))
        self.comboBox.setItemText(1, QCoreApplication.translate("LogDialog", u"Error", None))
        self.comboBox.setItemText(2, QCoreApplication.translate("LogDialog", u"Warning", None))
        self.comboBox.setItemText(3, QCoreApplication.translate("LogDialog", u"Info", None))
        self.comboBox.setItemText(4, QCoreApplication.translate("LogDialog", u"Debug", None))

        self.comboBox.setCurrentText(QCoreApplication.translate("LogDialog", u"Critical", None))
        self.saveLogButton.setText(QCoreApplication.translate("LogDialog", u"Save...", None))
    # retranslateUi

