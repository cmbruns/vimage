# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'vimage.ui'
##
## Created by: Qt User Interface Compiler version 6.2.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QMenuBar,
    QSizePolicy, QStatusBar, QToolBar, QVBoxLayout,
    QWidget)

from vmg.image_widget_gl import ImageWidgetGL

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(640, 549)
        MainWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.actionOpen = QAction(MainWindow)
        self.actionOpen.setObjectName(u"actionOpen")
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionExit.setMenuRole(QAction.QuitRole)
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionNext = QAction(MainWindow)
        self.actionNext.setObjectName(u"actionNext")
        self.actionNext.setEnabled(False)
        self.actionPrevious = QAction(MainWindow)
        self.actionPrevious.setObjectName(u"actionPrevious")
        self.actionPrevious.setEnabled(False)
        self.actionSharp = QAction(MainWindow)
        self.actionSharp.setObjectName(u"actionSharp")
        self.actionSharp.setCheckable(True)
        self.actionSharp.setChecked(True)
        self.actionBilinear = QAction(MainWindow)
        self.actionBilinear.setObjectName(u"actionBilinear")
        self.actionBilinear.setCheckable(True)
        self.actionSmooth = QAction(MainWindow)
        self.actionSmooth.setObjectName(u"actionSmooth")
        self.actionSmooth.setCheckable(True)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.imageWidgetGL = ImageWidgetGL(self.centralwidget)
        self.imageWidgetGL.setObjectName(u"imageWidgetGL")

        self.verticalLayout.addWidget(self.imageWidgetGL)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 640, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuOpen_Recent = QMenu(self.menuFile)
        self.menuOpen_Recent.setObjectName(u"menuOpen_Recent")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        self.menuSharp_Pixels = QMenu(self.menuView)
        self.menuSharp_Pixels.setObjectName(u"menuSharp_Pixels")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName(u"toolBar")
        MainWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.menuOpen_Recent.menuAction())
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuView.addAction(self.actionNext)
        self.menuView.addAction(self.actionPrevious)
        self.menuView.addAction(self.menuSharp_Pixels.menuAction())
        self.menuSharp_Pixels.addAction(self.actionSharp)
        self.menuSharp_Pixels.addAction(self.actionBilinear)
        self.menuSharp_Pixels.addAction(self.actionSmooth)
        self.toolBar.addAction(self.actionOpen)
        self.toolBar.addAction(self.actionSave_As)
        self.toolBar.addAction(self.actionPrevious)
        self.toolBar.addAction(self.actionNext)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        self.actionOpen.setText(QCoreApplication.translate("MainWindow", u"Open...", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Save As...", None))
        self.actionNext.setText(QCoreApplication.translate("MainWindow", u"Next", None))
#if QT_CONFIG(shortcut)
        self.actionNext.setShortcut(QCoreApplication.translate("MainWindow", u"Right", None))
#endif // QT_CONFIG(shortcut)
        self.actionPrevious.setText(QCoreApplication.translate("MainWindow", u"Previous", None))
#if QT_CONFIG(shortcut)
        self.actionPrevious.setShortcut(QCoreApplication.translate("MainWindow", u"Left", None))
#endif // QT_CONFIG(shortcut)
        self.actionSharp.setText(QCoreApplication.translate("MainWindow", u"Sharp", None))
        self.actionBilinear.setText(QCoreApplication.translate("MainWindow", u"Bilinear", None))
        self.actionSmooth.setText(QCoreApplication.translate("MainWindow", u"Smooth", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuOpen_Recent.setTitle(QCoreApplication.translate("MainWindow", u"Open Recent", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        self.menuSharp_Pixels.setTitle(QCoreApplication.translate("MainWindow", u"Sharp Pixels", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("MainWindow", u"toolBar", None))
        pass
    # retranslateUi

