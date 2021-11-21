import pkg_resources
import sys

from PIL import Image, ImageQt
from PySide6 import QtCore, QtGui, QtUiTools, QtWidgets

from vmg.recent_file import RecentFileList

Ui_MainWindow, MainWindowBase = QtUiTools.loadUiType(
    pkg_resources.resource_filename("vmg", "vimage.ui")
)


class VimageMainWindow(Ui_MainWindow, MainWindowBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.image = None
        self.recent_files = RecentFileList(
            open_file_slot=self.load_image,
            settings_key="recent_files",
            menu=self.menuOpen_Recent,
        )

    def load_image(self, file_name: str) -> None:
        self.image = Image.open(file_name)
        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(ImageQt.ImageQt(self.image)))
        self.setWindowFilePath(file_name)
        self.recent_files.add_file(file_name)

    @QtCore.Slot()
    def on_actionSave_As_triggered(self):
        file_path, file_filter = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image to File",
            filter="All files (*)",
        )
        if len(file_path) < 1:
            return
        self.image.save(file_path)
        # TODO: message about save

    @QtCore.Slot()
    def on_actionExit_triggered(self):
        QtWidgets.QApplication.quit()

    @QtCore.Slot()
    def on_actionOpen_triggered(self):
        file_name, filter_used = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Choose a file",
            filter="All files (*)",
        )
        if len(file_name) < 1:
            return
        self.load_image(file_name)


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
