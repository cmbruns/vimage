import pathlib

from PIL import Image
from PySide6 import QtWidgets, QtCore

from vmg.recent_file import RecentFileList
from vmg.ui_vimage import Ui_MainWindow


class VimageMainWindow(Ui_MainWindow, QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.image_list = []
        self.image_index = 0
        self.image = None
        self.recent_files = RecentFileList(
            open_file_slot=self.load_main_image,
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
        f = str(file_name)
        self.image = Image.open(f)
        self.imageWidget.set_image(self.image)
        self.set_current_image_path(f)
        self.statusbar.showMessage(f"Loaded image {file_name}", 5000)

    def load_main_image(self, file_name: str):
        path = pathlib.Path(file_name)
        name = path.name
        paths_list = [path, ]
        folder = path.parent.absolute()
        for file in folder.glob("*.*"):
            if file.name == name:
                continue  # Skip the triggering file
            if file.suffix.lower() in (".png", ".jpg",):  # TODO: is_image
                paths_list.append(file)
        self.set_image_list(paths_list, 0)

    def set_current_image_path(self, path: str):
        self.setWindowFilePath(path)
        self.recent_files.add_file(path)

    def set_image_list(self, image_list: list, current_index: int):
        if len(image_list) < 1:
            return
        self.image_list[:] = image_list[:]
        self.image_index = current_index
        self.load_image(self.image_list[current_index])
        self.update_previous_next()

    def update_previous_next(self):
        if self.image_index < len(self.image_list) - 1:
            self.actionNext.setEnabled(True)
            self.actionNext.setToolTip(str(self.image_list[self.image_index + 1]))
        else:
            self.actionNext.setEnabled(False)
        if self.image_index > 0:
            self.actionPrevious.setEnabled(True)
            self.actionPrevious.setToolTip(str(self.image_list[self.image_index - 1]))
        else:
            self.actionPrevious.setEnabled(False)

    @QtCore.Slot()
    def on_actionExit_triggered(self):
        QtWidgets.QApplication.quit()

    @QtCore.Slot()
    def on_actionNext_triggered(self):
        if self.image_index >= len(self.image_list) - 1:
            self.actionNext.setEnabled(False)
            return
        self.image_index += 1
        self.load_image(self.image_list[self.image_index])
        self.update_previous_next()

    @QtCore.Slot()
    def on_actionOpen_triggered(self):
        file_name, filter_used = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Choose a file",
            filter="All files (*)",
        )
        if len(file_name) < 1:
            return
        self.load_main_image(file_name)

    @QtCore.Slot()
    def on_actionPrevious_triggered(self):
        if self.image_index < 1 or len(self.image_list) < 1:
            self.actionPrevious.setEnabled(False)
            return
        self.image_index -= 1
        self.load_image(self.image_list[self.image_index])
        self.update_previous_next()

    @QtCore.Slot()
    def on_actionSave_As_triggered(self):
        file_path, file_filter = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image to File",
            filter="PNG Files (*.png);;JPEG Files(*.jpg);;All files (*.*)",
            selectedFilter="PNG Files (*.png)",
        )
        if len(file_path) < 1:
            return
        try:
            self.image.save(file_path)
            self.set_current_image_path(file_path)
            self.statusbar.showMessage(f"Saved image {file_path}", 5000)
        except ValueError as value_error:
            QtWidgets.QMessageBox.warning(
                parent=self,
                title="Error saving image with that name",
                text=f"Error: {str(value_error)}",
            )
