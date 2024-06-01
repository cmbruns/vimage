
import PIL
import io
import pathlib
from PIL import Image
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from vmg.natural_sort import natural_sort_key
from vmg.pixel_filter import PixelFilter
from vmg.projection_360 import Projection360
from vmg.recent_file import RecentFileList
from vmg.ui_vimage import Ui_MainWindow


_max_image_pixels = 1789569700
if Image.MAX_IMAGE_PIXELS is not None and Image.MAX_IMAGE_PIXELS < _max_image_pixels:
    Image.MAX_IMAGE_PIXELS = _max_image_pixels


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
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
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
        #
        self.imageWidgetGL.pixel_filter = PixelFilter.CATMULL_ROM
        # Allow action shortcuts even when toolbar and menu bar are hidden
        self.addAction(self.actionNext)
        self.addAction(self.actionPrevious)
        self.addAction(self.actionNormal_View)
        self.addAction(self.actionFull_Screen)
        self.addAction(self.actionSharp)
        # Make projections mutually exclusive
        self.projection_group = QtGui.QActionGroup(self)
        self.projection_group.addAction(self.actionPerspective)
        self.projection_group.addAction(self.actionStereographic)
        self.projection_group.addAction(self.actionEquidistant)
        self.projection_group.addAction(self.actionEquirectangular)
        #
        self.imageWidgetGL.request_message.connect(self.statusbar.showMessage)

    def activate_indexed_image(self):
        try:
            self.load_image(self.image_list[self.image_index])
        except PIL.UnidentifiedImageError as uie:
            self.statusbar.showMessage(str(uie), 5000)
        self.update_previous_next()

    def _dialog_and_save_image(self, image):
        file_path, _file_filter = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image to File",
            filter="PNG Files (*.png);;JPEG Files(*.jpg *.jpeg);;All files (*.*)",
            selectedFilter="PNG Files (*.png)",
        )
        if len(file_path) < 1:
            return
        try:
            self.save_image(file_path, image)
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

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file = url.toLocalFile()
                if pathlib.Path(file).is_file():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        mime_data = event.mimeData()
        files = []
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file = url.toLocalFile()
                if pathlib.Path(file).is_file():
                    files.append(file)
        if len(files) < 1:
            return
        elif len(files) == 1:
            self.load_main_image(files[0])
        else:
            self.set_image_list(files, 0)
        event.acceptProposedAction()
        self.activateWindow()  # Take focus immediately after successful drop

    def load_image(self, file_name: str) -> None:
        f = str(file_name)
        # TODO: separate thread cancellable loading
        with ScopedWaitCursor() as _:
            self.image = Image.open(f)
            self.imageWidgetGL.set_image(self.image)
            self.set_current_image_path(f)
            self.statusbar.showMessage(f"Loaded image {file_name}", 5000)
            self.actionSave_As.setEnabled(True)
            self.actionSave_Current_View_As.setEnabled(True)

    def load_main_image(self, file_name: str):
        path = pathlib.Path(file_name)
        name = path.name
        paths_list = [path, ]
        folder = path.parent.absolute()
        for file in folder.glob("*.*"):
            if file.name == name:
                continue  # Skip the triggering file
            if file.suffix.lower() in (".png", ".jpg", ".jpeg"):  # TODO: is_image
                paths_list.append(file)
        self.set_image_list(paths_list, 0)

    def save_image(self, file_path: str, image=None):
        if image is None:
            image = self.image
        # TODO: cancellable separate thread save? (at least after in-memory copy is made)
        with ScopedWaitCursor():
            self.statusbar.showMessage(f"Saving image {file_path}...", 5000)
            QtCore.QCoreApplication.processEvents()  # Make sure the message is shown
            # Avoid creating corrupt file by first writing to memory to check for writing errors
            in_memory_image = io.BytesIO()
            in_memory_image.name = file_path
            try:
                image.save(in_memory_image)
            except OSError:
                rgb_image = image.convert("RGB")  # TODO: choose bg color or warn or whatever
                rgb_image.save(in_memory_image)
            with open(file_path, "wb") as out:
                in_memory_image.seek(0)
                out.write(in_memory_image.read())
            if image is self.image:
                self.set_current_image_path(file_path)
                self.load_main_image(file_path)
            self.statusbar.showMessage(f"Saved image {file_path}", 5000)

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

    def set_360_projection(self, projection: Projection360) -> None:
        if self.imageWidgetGL.sphere_view_state.projection == projection:
            return
        self.imageWidgetGL.sphere_view_state.projection = projection
        self.imageWidgetGL.update()

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

    @QtCore.Slot(str)  # noqa
    def file_open_event(self, file_: str):
        self.load_main_image(file_)

    @QtCore.Slot(bool)  # noqa
    def on_actionEquidistant_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.EQUIDISTANT)

    @QtCore.Slot(bool)  # noqa
    def on_actionEquirectangular_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.EQUIRECTANGULAR)

    @QtCore.Slot()  # noqa
    def on_actionExit_triggered(self):  # noqa
        QtWidgets.QApplication.quit()

    @QtCore.Slot(bool)  # noqa
    def on_actionFull_Screen_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.menubar.hide()
            self.toolBar.hide()
            self.statusbar.hide()
            self.showFullScreen()
        else:
            self.menubar.show()
            self.toolBar.show()
            self.statusbar.show()
            self.showNormal()

    @QtCore.Slot(bool)  # noqa
    def on_actionPerspective_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.GNOMONIC)

    @QtCore.Slot()  # noqa
    def on_actionNext_triggered(self):  # noqa
        if self.image_index >= len(self.image_list) - 1:
            self.actionNext.setEnabled(False)
            return
        self.image_index += 1
        self.activate_indexed_image()

    @QtCore.Slot()  # noqa
    def on_actionNormal_View_triggered(self):  # noqa
        self.actionFull_Screen.setChecked(False)

    @QtCore.Slot()  # noqa
    def on_actionOpen_triggered(self):  # noqa
        file_name, filter_used = QFileDialog.getOpenFileName(
            parent=self,
            caption="Choose a file",
            filter="All files (*)",
        )
        if len(file_name) < 1:
            return
        self.load_main_image(file_name)

    @QtCore.Slot()  # noqa
    def on_actionPrevious_triggered(self):  # noqa
        if self.image_index < 1 or len(self.image_list) < 1:
            self.actionPrevious.setEnabled(False)
            return
        self.image_index -= 1
        self.activate_indexed_image()

    @QtCore.Slot()  # noqa
    def on_actionSave_As_triggered(self):  # noqa
        self._dialog_and_save_image(self.image)

    @QtCore.Slot()  # noqa
    def on_actionSave_Current_View_As_triggered(self):  # noqa
        pixmap = self.imageWidgetGL.grab()
        view_image = Image.fromqpixmap(pixmap)
        self._dialog_and_save_image(view_image)

    @QtCore.Slot(bool)  # noqa
    def on_actionSharp_toggled(self, is_checked: bool):  # noqa
        if is_checked and self.imageWidgetGL.pixel_filter == PixelFilter.SHARP:
            return
        if not is_checked and self.imageWidgetGL.pixel_filter == PixelFilter.CATMULL_ROM:
            return
        if is_checked:
            self.imageWidgetGL.pixel_filter = PixelFilter.SHARP
        else:
            self.imageWidgetGL.pixel_filter = PixelFilter.CATMULL_ROM
        self.imageWidgetGL.update()

    @QtCore.Slot(bool)  # noqa
    def on_actionStereographic_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.STEREOGRAPHIC)
