# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'lens_parameters_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.2.1
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
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QGridLayout,
    QLabel, QSizePolicy)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(215, 68)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.fov_doubleSpinBox = QDoubleSpinBox(Dialog)
        self.fov_doubleSpinBox.setObjectName(u"fov_doubleSpinBox")
        self.fov_doubleSpinBox.setDecimals(2)
        self.fov_doubleSpinBox.setMinimum(90.000000000000000)
        self.fov_doubleSpinBox.setMaximum(360.000000000000000)
        self.fov_doubleSpinBox.setSingleStep(0.200000000000000)
        self.fov_doubleSpinBox.setValue(195.000000000000000)

        self.gridLayout.addWidget(self.fov_doubleSpinBox, 0, 1, 1, 1)

        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.lensrot_doubleSpinBox = QDoubleSpinBox(Dialog)
        self.lensrot_doubleSpinBox.setObjectName(u"lensrot_doubleSpinBox")
        self.lensrot_doubleSpinBox.setDecimals(2)
        self.lensrot_doubleSpinBox.setMinimum(-180.000000000000000)
        self.lensrot_doubleSpinBox.setMaximum(180.000000000000000)
        self.lensrot_doubleSpinBox.setSingleStep(0.100000000000000)

        self.gridLayout.addWidget(self.lensrot_doubleSpinBox, 1, 1, 1, 1)

#if QT_CONFIG(shortcut)
        self.label.setBuddy(self.fov_doubleSpinBox)
        self.label_2.setBuddy(self.lensrot_doubleSpinBox)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dual Fisheye Lens Parameters", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"fisheye field of view", None))
        self.fov_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"interlens axial rotation", None))
        self.lensrot_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
    # retranslateUi

