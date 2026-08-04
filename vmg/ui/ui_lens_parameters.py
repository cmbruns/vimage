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
    QGroupBox, QLabel, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(375, 272)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.widget = QWidget(Dialog)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_2 = QVBoxLayout(self.widget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.groupBox_2 = QGroupBox(self.widget)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.gridLayout_2 = QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_3 = QLabel(self.groupBox_2)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 0, 0, 1, 1)

        self.poseRoll_doubleSpinBox = QDoubleSpinBox(self.groupBox_2)
        self.poseRoll_doubleSpinBox.setObjectName(u"poseRoll_doubleSpinBox")
        self.poseRoll_doubleSpinBox.setWrapping(True)
        self.poseRoll_doubleSpinBox.setMinimum(-180.000000000000000)
        self.poseRoll_doubleSpinBox.setMaximum(180.000000000000000)
        self.poseRoll_doubleSpinBox.setSingleStep(0.250000000000000)

        self.gridLayout_2.addWidget(self.poseRoll_doubleSpinBox, 0, 1, 1, 1)

        self.label_4 = QLabel(self.groupBox_2)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_2.addWidget(self.label_4, 1, 0, 1, 1)

        self.posePitch_doubleSpinBox = QDoubleSpinBox(self.groupBox_2)
        self.posePitch_doubleSpinBox.setObjectName(u"posePitch_doubleSpinBox")
        self.posePitch_doubleSpinBox.setMinimum(-90.000000000000000)
        self.posePitch_doubleSpinBox.setMaximum(90.000000000000000)
        self.posePitch_doubleSpinBox.setSingleStep(0.250000000000000)

        self.gridLayout_2.addWidget(self.posePitch_doubleSpinBox, 1, 1, 1, 1)

        self.label_5 = QLabel(self.groupBox_2)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 2, 0, 1, 1)

        self.poseHeading_doubleSpinBox = QDoubleSpinBox(self.groupBox_2)
        self.poseHeading_doubleSpinBox.setObjectName(u"poseHeading_doubleSpinBox")
        self.poseHeading_doubleSpinBox.setWrapping(True)
        self.poseHeading_doubleSpinBox.setMinimum(0.000000000000000)
        self.poseHeading_doubleSpinBox.setMaximum(360.000000000000000)
        self.poseHeading_doubleSpinBox.setSingleStep(0.250000000000000)

        self.gridLayout_2.addWidget(self.poseHeading_doubleSpinBox, 2, 1, 1, 1)


        self.verticalLayout_2.addWidget(self.groupBox_2)

        self.groupBox = QGroupBox(self.widget)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout = QGridLayout(self.groupBox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.fov_doubleSpinBox = QDoubleSpinBox(self.groupBox)
        self.fov_doubleSpinBox.setObjectName(u"fov_doubleSpinBox")
        self.fov_doubleSpinBox.setDecimals(2)
        self.fov_doubleSpinBox.setMinimum(90.000000000000000)
        self.fov_doubleSpinBox.setMaximum(360.000000000000000)
        self.fov_doubleSpinBox.setSingleStep(0.200000000000000)
        self.fov_doubleSpinBox.setValue(195.000000000000000)

        self.gridLayout.addWidget(self.fov_doubleSpinBox, 0, 1, 1, 1)

        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.lensrot_doubleSpinBox = QDoubleSpinBox(self.groupBox)
        self.lensrot_doubleSpinBox.setObjectName(u"lensrot_doubleSpinBox")
        self.lensrot_doubleSpinBox.setDecimals(2)
        self.lensrot_doubleSpinBox.setMinimum(-180.000000000000000)
        self.lensrot_doubleSpinBox.setMaximum(180.000000000000000)
        self.lensrot_doubleSpinBox.setSingleStep(0.100000000000000)

        self.gridLayout.addWidget(self.lensrot_doubleSpinBox, 1, 1, 1, 1)


        self.verticalLayout_2.addWidget(self.groupBox)

        self.verticalSpacer = QSpacerItem(20, 21, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.verticalLayout.addWidget(self.widget)

#if QT_CONFIG(shortcut)
        self.label.setBuddy(self.fov_doubleSpinBox)
        self.label_2.setBuddy(self.lensrot_doubleSpinBox)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Camera Settings", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("Dialog", u"Camera Pose", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"Roll", None))
        self.poseRoll_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
        self.label_4.setText(QCoreApplication.translate("Dialog", u"Pitch", None))
        self.posePitch_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
        self.label_5.setText(QCoreApplication.translate("Dialog", u"Heading", None))
        self.poseHeading_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
        self.groupBox.setTitle(QCoreApplication.translate("Dialog", u"Dual Fisheye Lens Parameters", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"Inscribed Field of View", None))
        self.fov_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"Interlens Axial Rotation", None))
        self.lensrot_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u"\u00b0", None))
    # retranslateUi

