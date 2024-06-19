# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'vimage.ui'
##
## Created by: Qt User Interface Compiler version 6.2.4
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
        self.actionPerspective = QAction(MainWindow)
        self.actionPerspective.setObjectName(u"actionPerspective")
        self.actionPerspective.setCheckable(True)
        self.actionEquirectangular = QAction(MainWindow)
        self.actionEquirectangular.setObjectName(u"actionEquirectangular")
        self.actionEquirectangular.setCheckable(True)
        self.actionPaste = QAction(MainWindow)
        self.actionPaste.setObjectName(u"actionPaste")
        self.actionPaste.setEnabled(False)
        self.actionCopy = QAction(MainWindow)
        self.actionCopy.setObjectName(u"actionCopy")
        self.actionReset_View = QAction(MainWindow)
        self.actionReset_View.setObjectName(u"actionReset_View")
        self.actionSelect_Rectangle = QAction(MainWindow)
        self.actionSelect_Rectangle.setObjectName(u"actionSelect_Rectangle")
        self.actionSelect_Rectangle.setEnabled(False)
        self.actionCrop_to_Selection = QAction(MainWindow)
        self.actionCrop_to_Selection.setObjectName(u"actionCrop_to_Selection")
        self.actionCrop_to_Selection.setEnabled(False)
        self.actionCrop_to_Current_View = QAction(MainWindow)
        self.actionCrop_to_Current_View.setObjectName(u"actionCrop_to_Current_View")
        self.actionCrop_to_Current_View.setEnabled(False)
        self.actionSelect_None = QAction(MainWindow)
        self.actionSelect_None.setObjectName(u"actionSelect_None")
        self.actionSelect_None.setEnabled(False)
        self.actionZoom_Out = QAction(MainWindow)
        self.actionZoom_Out.setObjectName(u"actionZoom_Out")
        self.actionZoom_Out.setEnabled(False)
        self.actionZoom_In = QAction(MainWindow)
        self.actionZoom_In.setObjectName(u"actionZoom_In")
        self.actionZoom_In.setEnabled(False)
        self.actionReport_a_Problem = QAction(MainWindow)
        self.actionReport_a_Problem.setObjectName(u"actionReport_a_Problem")
        self.actionReport_a_Problem.setEnabled(False)
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
        self.menu360_Projection.setEnabled(False)
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        self.menuEdit = QMenu(self.menubar)
        self.menuEdit.setObjectName(u"menuEdit")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName(u"toolBar")
        MainWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.menuOpen_Recent.menuAction())
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addAction(self.actionSave_Current_View_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuView.addAction(self.actionReset_View)
        self.menuView.addAction(self.actionZoom_Out)
        self.menuView.addAction(self.actionZoom_In)
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionPrevious)
        self.menuView.addAction(self.actionNext)
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionSharp)
        self.menuView.addAction(self.actionFull_Screen)
        self.menuView.addAction(self.menu360_Projection.menuAction())
        self.menu360_Projection.addAction(self.actionPerspective)
        self.menu360_Projection.addAction(self.actionStereographic)
        self.menu360_Projection.addAction(self.actionEquidistant)
        self.menu360_Projection.addAction(self.actionEquirectangular)
        self.menuHelp.addAction(self.actionAbout)
        self.menuHelp.addAction(self.actionReport_a_Problem)
        self.menuEdit.addAction(self.actionCrop_to_Current_View)
        self.menuEdit.addAction(self.actionCrop_to_Selection)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionCopy)
        self.menuEdit.addAction(self.actionPaste)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionSelect_Rectangle)
        self.menuEdit.addAction(self.actionSelect_None)
        self.toolBar.addAction(self.actionOpen)
        self.toolBar.addAction(self.actionSave_As)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPrevious)
        self.toolBar.addAction(self.actionNext)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        self.actionOpen.setText(QCoreApplication.translate("MainWindow", u"Open...", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Save As...", None))
        self.actionNext.setText(QCoreApplication.translate("MainWindow", u"Next Image", None))
#if QT_CONFIG(shortcut)
        self.actionNext.setShortcut(QCoreApplication.translate("MainWindow", u"Right", None))
#endif // QT_CONFIG(shortcut)
        self.actionPrevious.setText(QCoreApplication.translate("MainWindow", u"Previous Image", None))
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
        self.actionStereographic.setText(QCoreApplication.translate("MainWindow", u"Stereographic", None))
#if QT_CONFIG(tooltip)
        self.actionStereographic.setToolTip(QCoreApplication.translate("MainWindow", u"Stereographic projection preserves the shapes and angles of objects. This can be used to make \"small world\" images. The image is unbounded and the field of view is limited to less than 360 degrees.", None))
#endif // QT_CONFIG(tooltip)
        self.actionEquidistant.setText(QCoreApplication.translate("MainWindow", u"Equidistant", None))
#if QT_CONFIG(tooltip)
        self.actionEquidistant.setToolTip(QCoreApplication.translate("MainWindow", u"Equidistant projection can show the entire panorama within a circular boundary. Distances from the center point are proportional to the true angle from the center point.", None))
#endif // QT_CONFIG(tooltip)
        self.actionPerspective.setText(QCoreApplication.translate("MainWindow", u"Perspective", None))
#if QT_CONFIG(tooltip)
        self.actionPerspective.setToolTip(QCoreApplication.translate("MainWindow", u"Perspective projection is similar to plain old non-360 non-fisheye photos. Straight lines in the real world remain straight in this projection. The image is unbounded and the field of view is limited to less than 180 degrees.", None))
#endif // QT_CONFIG(tooltip)
        self.actionEquirectangular.setText(QCoreApplication.translate("MainWindow", u"Equirectangular", None))
#if QT_CONFIG(tooltip)
        self.actionEquirectangular.setToolTip(QCoreApplication.translate("MainWindow", u"Equirectangular projection can show the entire panorama within a rectangle. This projection is often used as the internal storage format for 360 images.", None))
#endif // QT_CONFIG(tooltip)
        self.actionPaste.setText(QCoreApplication.translate("MainWindow", u"Paste", None))
        self.actionCopy.setText(QCoreApplication.translate("MainWindow", u"Copy", None))
        self.actionReset_View.setText(QCoreApplication.translate("MainWindow", u"Reset View", None))
        self.actionSelect_Rectangle.setText(QCoreApplication.translate("MainWindow", u"Select Rectangle", None))
#if QT_CONFIG(tooltip)
        self.actionSelect_Rectangle.setToolTip(QCoreApplication.translate("MainWindow", u"Select a rectangular region", None))
#endif // QT_CONFIG(tooltip)
        self.actionCrop_to_Selection.setText(QCoreApplication.translate("MainWindow", u"Crop to Selection", None))
        self.actionCrop_to_Current_View.setText(QCoreApplication.translate("MainWindow", u"Crop to Current View", None))
        self.actionSelect_None.setText(QCoreApplication.translate("MainWindow", u"Select None", None))
        self.actionZoom_Out.setText(QCoreApplication.translate("MainWindow", u"Zoom Out", None))
        self.actionZoom_In.setText(QCoreApplication.translate("MainWindow", u"Zoom In", None))
        self.actionReport_a_Problem.setText(QCoreApplication.translate("MainWindow", u"Report a Problem...", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuOpen_Recent.setTitle(QCoreApplication.translate("MainWindow", u"Open Recent", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        self.menu360_Projection.setTitle(QCoreApplication.translate("MainWindow", u"360 Projection", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
        self.menuEdit.setTitle(QCoreApplication.translate("MainWindow", u"Edit", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("MainWindow", u"toolBar", None))
        pass
    # retranslateUi

