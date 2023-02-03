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
        MainWindow.resize(719, 577)
        MainWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.actionOpen = QAction(MainWindow)
        self.actionOpen.setObjectName(u"actionOpen")
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionExit.setMenuRole(QAction.QuitRole)
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionSave_As.setEnabled(False)
        self.actionNext = QAction(MainWindow)
        self.actionNext.setObjectName(u"actionNext")
        self.actionNext.setEnabled(False)
        self.actionPrevious = QAction(MainWindow)
        self.actionPrevious.setObjectName(u"actionPrevious")
        self.actionPrevious.setEnabled(False)
        self.actionSharp = QAction(MainWindow)
        self.actionSharp.setObjectName(u"actionSharp")
        self.actionSharp.setCheckable(True)
        self.actionSharp.setChecked(False)
        self.actionFull_Screen = QAction(MainWindow)
        self.actionFull_Screen.setObjectName(u"actionFull_Screen")
        self.actionFull_Screen.setCheckable(True)
        self.actionNormal_View = QAction(MainWindow)
        self.actionNormal_View.setObjectName(u"actionNormal_View")
        self.actionNormal_View.setEnabled(True)
        self.actionNormal_View.setVisible(True)
        self.actionRun_Test = QAction(MainWindow)
        self.actionRun_Test.setObjectName(u"actionRun_Test")
        self.actionAbout = QAction(MainWindow)
        self.actionAbout.setObjectName(u"actionAbout")
        self.actionAbout.setMenuRole(QAction.AboutRole)
        self.actionSave_Current_View_As = QAction(MainWindow)
        self.actionSave_Current_View_As.setObjectName(u"actionSave_Current_View_As")
        self.actionSave_Current_View_As.setEnabled(False)
        self.actionStereographic = QAction(MainWindow)
        self.actionStereographic.setObjectName(u"actionStereographic")
        self.actionStereographic.setCheckable(True)
        self.actionStereographic.setChecked(True)
        self.actionEquidistant = QAction(MainWindow)
        self.actionEquidistant.setObjectName(u"actionEquidistant")
        self.actionEquidistant.setCheckable(True)
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
        self.menubar.setGeometry(QRect(0, 0, 719, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuOpen_Recent = QMenu(self.menuFile)
        self.menuOpen_Recent.setObjectName(u"menuOpen_Recent")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        self.menu360_Projection = QMenu(self.menuView)
        self.menu360_Projection.setObjectName(u"menu360_Projection")
        self.menuTest = QMenu(self.menubar)
        self.menuTest.setObjectName(u"menuTest")
        self.menuTest.setEnabled(False)
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName(u"toolBar")
        MainWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuTest.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.menuOpen_Recent.menuAction())
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addAction(self.actionSave_Current_View_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuView.addAction(self.actionNext)
        self.menuView.addAction(self.actionPrevious)
        self.menuView.addAction(self.actionSharp)
        self.menuView.addAction(self.actionFull_Screen)
        self.menuView.addAction(self.menu360_Projection.menuAction())
        self.menu360_Projection.addAction(self.actionStereographic)
        self.menu360_Projection.addAction(self.actionEquidistant)
        self.menuTest.addAction(self.actionRun_Test)
        self.menuHelp.addAction(self.actionAbout)
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
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Save Original Image As...", None))
        self.actionNext.setText(QCoreApplication.translate("MainWindow", u"Next", None))
#if QT_CONFIG(shortcut)
        self.actionNext.setShortcut(QCoreApplication.translate("MainWindow", u"Right", None))
#endif // QT_CONFIG(shortcut)
        self.actionPrevious.setText(QCoreApplication.translate("MainWindow", u"Previous", None))
#if QT_CONFIG(shortcut)
        self.actionPrevious.setShortcut(QCoreApplication.translate("MainWindow", u"Left", None))
#endif // QT_CONFIG(shortcut)
        self.actionSharp.setText(QCoreApplication.translate("MainWindow", u"Sharp Pixels", None))
#if QT_CONFIG(shortcut)
        self.actionSharp.setShortcut(QCoreApplication.translate("MainWindow", u"S", None))
#endif // QT_CONFIG(shortcut)
        self.actionFull_Screen.setText(QCoreApplication.translate("MainWindow", u"Full Screen", None))
#if QT_CONFIG(shortcut)
        self.actionFull_Screen.setShortcut(QCoreApplication.translate("MainWindow", u"F", None))
#endif // QT_CONFIG(shortcut)
        self.actionNormal_View.setText(QCoreApplication.translate("MainWindow", u"Normal View", None))
#if QT_CONFIG(shortcut)
        self.actionNormal_View.setShortcut(QCoreApplication.translate("MainWindow", u"Esc", None))
#endif // QT_CONFIG(shortcut)
        self.actionRun_Test.setText(QCoreApplication.translate("MainWindow", u"Run Test", None))
        self.actionAbout.setText(QCoreApplication.translate("MainWindow", u"About", None))
        self.actionSave_Current_View_As.setText(QCoreApplication.translate("MainWindow", u"Save Current View As...", None))
        self.actionStereographic.setText(QCoreApplication.translate("MainWindow", u"Stereographic (Small World)", None))
        self.actionEquidistant.setText(QCoreApplication.translate("MainWindow", u"Equidistant (Circular)", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuOpen_Recent.setTitle(QCoreApplication.translate("MainWindow", u"Open Recent", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        self.menu360_Projection.setTitle(QCoreApplication.translate("MainWindow", u"360 Projection", None))
        self.menuTest.setTitle(QCoreApplication.translate("MainWindow", u"Test", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("MainWindow", u"toolBar", None))
        pass
    # retranslateUi

