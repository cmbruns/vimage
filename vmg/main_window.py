import io
import pathlib

import PIL
from PIL import Image
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from vmg.natural_sort import natural_sort_key
from vmg.recent_file import RecentFileList
from vmg.ui_vimage import Ui_MainWindow


class ScopedWaitCursor(object):
    def __init__(self):
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        QtWidgets.QApplication.restoreOverrideCursor()


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
        with ScopedWaitCursor() as _:
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
        current_item = image_list[current_index]
        self.image_list = sorted(image_list, key=natural_sort_key)
        self.image_index = None
        for index, item in enumerate(self.image_list):
            if item is current_item:
                self.image_index = index
        assert self.image_index is not None
        self.load_image(self.image_list[self.image_index])
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
        self.activate_indexed_image()

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
        self.activate_indexed_image()

    def activate_indexed_image(self):
        try:
            self.load_image(self.image_list[self.image_index])
        except PIL.UnidentifiedImageError as uie:
            self.statusbar.showMessage(str(uie), 5000)
        self.update_previous_next()

    def save_image(self, file_path: str):
        with ScopedWaitCursor() as swc:
            # Avoid creating corrupt file by first writing to memory to check for writing errors
            in_memory_image = io.BytesIO()
            in_memory_image.name = file_path
            self.image.save(in_memory_image)
            with open(file_path, "wb") as out:
                in_memory_image.seek(0)
                out.write(in_memory_image.read())
            self.set_current_image_path(file_path)
            self.load_main_image(file_path)
            self.statusbar.showMessage(f"Saved image {file_path}", 5000)

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
            self.save_image(file_path)
        except ValueError as value_error:  # File without extension
            QtWidgets.QMessageBox.warning(
                self,
                "Error saving image with that name",
                f"Error: {str(value_error)}",
            )
        except OSError as os_error:  # cannot write mode RGBA as JPEG
            QtWidgets.QMessageBox.warning(
                self,
                "Error saving image",
                f"Error: {str(os_error)}",
            )
        except Exception as exception:
            QtWidgets.QMessageBox.warning(
                self,
                "Error saving image",
                f"Error: {str(exception)}",
            )