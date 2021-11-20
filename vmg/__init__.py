import pkg_resources
import sys

from PIL import Image, ImageQt
from PySide6 import QtGui, QtUiTools, QtWidgets


Ui_MainWindow, MainWindowBase = QtUiTools.loadUiType(
    pkg_resources.resource_filename("vmg", "vimage.ui")
)


class VimageMainWindow(Ui_MainWindow, MainWindowBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.image = None

    def load_image(self, file_name: str) -> None:
        print(file_name)
        self.image = Image.open(file_name)
        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(ImageQt.ImageQt(self.image)))
        self.setWindowFilePath(file_name)


class VimageApp(object):
    def __init__(self):
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationDisplayName("vimage")
        window = VimageMainWindow()
        args = app.arguments()
        if len(args) > 1:
            window.load_image(args[1])
        window.show()
        sys.exit(app.exec())
