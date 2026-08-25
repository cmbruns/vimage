# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'demosaic_dialog.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QGroupBox,
    QRadioButton, QSizePolicy, QSpacerItem, QVBoxLayout)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(386, 205)
        self.verticalLayout_2 = QVBoxLayout(Dialog)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.groupBox = QGroupBox(Dialog)
        self.groupBox.setObjectName(u"groupBox")
        self.verticalLayout = QVBoxLayout(self.groupBox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.radioButtonLanczos7x7 = QRadioButton(self.groupBox)
        self.radioButtonLanczos7x7.setObjectName(u"radioButtonLanczos7x7")
        self.radioButtonLanczos7x7.setChecked(True)

        self.verticalLayout.addWidget(self.radioButtonLanczos7x7)

        self.radioButtonMalvar_He_Cutler_5x5 = QRadioButton(self.groupBox)
        self.radioButtonMalvar_He_Cutler_5x5.setObjectName(u"radioButtonMalvar_He_Cutler_5x5")

        self.verticalLayout.addWidget(self.radioButtonMalvar_He_Cutler_5x5)

        self.radioButtonLanczos_5x5_Green_Median_Chroma = QRadioButton(self.groupBox)
        self.radioButtonLanczos_5x5_Green_Median_Chroma.setObjectName(u"radioButtonLanczos_5x5_Green_Median_Chroma")

        self.verticalLayout.addWidget(self.radioButtonLanczos_5x5_Green_Median_Chroma)

        self.radioButtonBilinear_3x3 = QRadioButton(self.groupBox)
        self.radioButtonBilinear_3x3.setObjectName(u"radioButtonBilinear_3x3")

        self.verticalLayout.addWidget(self.radioButtonBilinear_3x3)


        self.verticalLayout_2.addWidget(self.groupBox)

        self.checkBoxShow_CFA_Colors = QCheckBox(Dialog)
        self.checkBoxShow_CFA_Colors.setObjectName(u"checkBoxShow_CFA_Colors")
        self.checkBoxShow_CFA_Colors.setChecked(True)

        self.verticalLayout_2.addWidget(self.checkBoxShow_CFA_Colors)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Color Filter Array Demosaicking", None))
        self.groupBox.setTitle(QCoreApplication.translate("Dialog", u"Demosaic Method", None))
        self.radioButtonLanczos7x7.setText(QCoreApplication.translate("Dialog", u"Lanczos 7x7", None))
        self.radioButtonMalvar_He_Cutler_5x5.setText(QCoreApplication.translate("Dialog", u"Malvar He Cutler (5x5)", None))
        self.radioButtonLanczos_5x5_Green_Median_Chroma.setText(QCoreApplication.translate("Dialog", u"Lanczos 5x5 green, Median Chroma", None))
        self.radioButtonBilinear_3x3.setText(QCoreApplication.translate("Dialog", u"Bilinear (3x3)", None))
        self.checkBoxShow_CFA_Colors.setText(QCoreApplication.translate("Dialog", u"Show CFA colors at high zoom", None))
    # retranslateUi

