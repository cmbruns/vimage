import sys

from PIL import Image, ImageQt
from PySide6 import QtCore, QtGui, QtWidgets

from vmg.recent_file import RecentFileList
from vmg.ui_vimage import Ui_MainWindow


class VimageMainWindow(Ui_MainWindow, QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.image = None
        self.recent_files = RecentFileList(
            open_file_slot=self.load_image,
            settings_key="recent_files",
            menu=self.menuOpen_Recent,
        )
        self.actionSave_As.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_DialogSaveButton))
        self.actionOpen.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_DialogOpenButton))
        self.actionPrevious.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_ArrowBack))
        self.actionNext.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_ArrowForward))

    def load_image(self, file_name: str) -> None:
        self.image = Image.open(file_name)
        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(ImageQt.ImageQt(self.image)))
        self.set_current_image_path(file_name)

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
        self.set_current_image_path(file_path)
        self.statusbar.showMessage(f"Saved image {file_path}", 5000)

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

    def set_current_image_path(self, path: str):
        self.setWindowFilePath(path)
        self.recent_files.add_file(path)


class VimageApp(object):
    def __init__(self):
        app = QtWidgets.QApplication(sys.argv)
        app.setOrganizationName("rotatingpenguin.com")
        app.setApplicationName("vimage")
        app.setApplicationDisplayName("vimage")
        window = VimageMainWindow()
        args = app.arguments()
        if len(args) > 1:
            window.load_image(args[1])
        window.show()
        sys.exit(app.exec())
