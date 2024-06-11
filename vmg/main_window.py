from inspect import cleandoc
import io
import os
from pathlib import Path
import time

import PIL
from pillow_heif import register_heif_opener
from PIL import Image, ImageGrab
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QFileDialog, QMessageBox

from vmg.circular_combo_box import CircularComboBox
from vmg.natural_sort import natural_sort_key
from vmg.pixel_filter import PixelFilter
from vmg.projection_360 import Projection360
from vmg.recent_file import RecentFileList
from vmg.ui_vimage import Ui_MainWindow


_max_image_pixels = 1789569700
if Image.MAX_IMAGE_PIXELS is not None and Image.MAX_IMAGE_PIXELS < _max_image_pixels:
    Image.MAX_IMAGE_PIXELS = _max_image_pixels
register_heif_opener()


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
        self.imageWidgetGL.pixel_filter = PixelFilter.CATMULL_ROM
        self.imageWidgetGL.request_message.connect(self.statusbar.showMessage)
        self.imageWidgetGL.signal_360.connect(self.set_is_360)
        # Configure actions
        self.recent_files = RecentFileList(
            open_file_slot=self.load_main_image,
            settings_key="recent_files",
            menu=self.menuOpen_Recent,
        )
        self.actionNext.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_ArrowForward))
        self.actionOpen.setShortcut(QtGui.QKeySequence.Open)
        self.actionOpen.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_DialogOpenButton))
        self.actionPrevious.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_ArrowBack))
        self.actionExit.setShortcut(QtGui.QKeySequence.Quit)
        self.actionSave_As.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.SP_DialogSaveButton))
        self.actionSave_As.setShortcut(QtGui.QKeySequence.SaveAs)
        #
        # Allow action shortcuts even when toolbar and menu bar are hidden
        self.addAction(self.actionNext)
        self.addAction(self.actionPrevious)
        self.addAction(self.actionNormal_View)
        self.addAction(self.actionFull_Screen)
        self.addAction(self.actionSharp)
        # Make projections mutually exclusive
        self.projection_group = QtGui.QActionGroup(self)
        self.projectionComboBox = CircularComboBox()
        for proj in (
                self.actionPerspective,
                self.actionStereographic,
                self.actionEquidistant,
                self.actionEquirectangular,
        ):
            self.projection_group.addAction(proj)
            self.projectionComboBox.addItem(proj.text(), proj)
            if proj.isChecked():
                self.projectionComboBox.setCurrentText(proj.text())
        self.projectionComboBox.setEnabled(False)
        self.projectionComboBox.currentIndexChanged.connect(self.projection_combo_box_current_index_changed)  # noqa
        # List label show progress through image list
        self.list_label = QtWidgets.QLabel("0/0")
        self.list_label.setMinimumWidth(40)
        self.toolBar.addWidget(self.list_label)
        self.toolBar.addSeparator()
        self.toolBar.addWidget(self.projectionComboBox)
        self.toolBar.toggleViewAction().setEnabled(False)  # I did not like accidentally hiding it
        # Clipboard actions
        self.clipboard = QtGui.QGuiApplication.clipboard()
        self.clipboard.dataChanged.connect(self.process_clipboard_change)  # noqa
        self.actionCopy.setEnabled(False)
        self.actionCopy.setShortcut(QtGui.QKeySequence.Copy)
        self.actionPaste.setEnabled(self.clipboard.image().width() > 0)
        self.actionPaste.setShortcut(QtGui.QKeySequence.Paste)
        self.clipboard.dataChanged.connect(self.process_clipboard_change)  # noqa
        # Undo actions
        self.undo_stack = QUndoStack()  # TODO: per-image undo stack
        self.undo_stack.cleanChanged.connect(self.undo_stack_clean_changed)  # noqa
        self.undo_stack.setActive()
        self.action_undo = self.undo_stack.createUndoAction(self)
        self.action_undo.setShortcut(QtGui.QKeySequence.Undo)
        self.action_redo = self.undo_stack.createRedoAction(self)
        self.action_redo.setShortcut(QtGui.QKeySequence.Redo)
        top_action = self.menuEdit.actions()[0]
        self.menuEdit.insertAction(top_action, self.action_undo)
        self.menuEdit.insertAction(top_action, self.action_redo)
        self.menuEdit.insertSeparator(top_action)

    def activate_indexed_image(self):
        try:
            self.load_image(self.image_list[self.image_index])
        except PIL.UnidentifiedImageError as uie:
            self.statusbar.showMessage(str(uie), 5000)
        self.update_previous_next()

    def _dialog_and_save_image(self, image) -> str:
        file_path, _file_filter = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image to File",
            filter="PNG Files (*.png);;JPEG Files(*.jpg *.jpeg);;All files (*.*)",
            selectedFilter="PNG Files (*.png)",
        )
        if len(file_path) < 1:
            return ""
        try:
            self.save_image(file_path, image)
            return file_path
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
        return ""

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file = url.toLocalFile()
                if Path(file).is_file():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        mime_data = event.mimeData()
        files = []
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file = url.toLocalFile()
                if Path(file).is_file():
                    files.append(file)
        if len(files) < 1:
            return
        elif len(files) == 1:
            self.load_main_image(files[0])
        else:
            self.set_image_list(files, 0)
        event.acceptProposedAction()
        self.activateWindow()  # Take focus immediately after successful drop

    def load_image_from_memory(self, image: PIL.Image.Image, name: str) -> bool:
        if image.width < 1:
            return False
        f = str(name)
        self.image = image
        # TODO: separate thread cancellable loading
        self.imageWidgetGL.set_image(self.image)
        self.set_current_image_path(f)
        self.statusbar.showMessage(f"Loaded image {name}", 5000)
        self.actionSave_As.setEnabled(True)
        self.actionSave_Current_View_As.setEnabled(True)
        self.actionCopy.setEnabled(True)
        return True

    def load_image(self, file_name: str) -> bool:
        with ScopedWaitCursor():
            image = Image.open(str(file_name))
            if self.load_image_from_memory(image=image, name=file_name):
                self.undo_stack.clear()
                self.undo_stack.setClean()  # clear() does not always set clean
                return True
        return False

    def load_main_image(self, file_name: str):
        path = Path(file_name)
        name = path.name
        paths_list = [path, ]
        folder = path.parent.absolute()
        for file in folder.glob("*.*"):
            if file.name == name:
                continue  # Skip the triggering file
            if file.suffix.lower() in (
                ".bmp",
                ".heic",
                ".heif",
                ".png",
                ".jpg",
                ".jpeg",
            ):  # TODO: is_image
                paths_list.append(file)
        self.set_image_list(paths_list, 0)

    @QtCore.Slot()  # noqa
    def process_clipboard_change(self):
        has_image = self.clipboard.image().width() > 0
        self.actionPaste.setEnabled(has_image)

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
        if os.path.exists(path):
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

    def set_360_projection(self, projection: Projection360, action: QtGui.QAction) -> None:
        if self.imageWidgetGL.sphere_view_state.projection == projection:
            return
        self.imageWidgetGL.sphere_view_state.projection = projection
        if self.projectionComboBox.currentText() != action.text():
            self.projectionComboBox.setCurrentText(action.text())
        self.imageWidgetGL.update()

    @QtCore.Slot(bool)  # noqa
    def set_is_360(self, is_360: bool) -> None:
        self.projectionComboBox.setEnabled(is_360)
        self.menu360_Projection.setEnabled(is_360)

    def update_previous_next(self):
        # Update progress label
        total = len(self.image_list)
        current = self.image_index + 1
        self.list_label.setText(f"{current}/{total}")
        #
        if len(self.image_list) < 2:
            for action in (self.actionPrevious, self.actionNext):
                action.setEnabled(False)
                action.setToolTip(action.text())
        else:
            next_index = (self.image_index + 1) % total
            prev_index = (self.image_index - 1 + total) % total
            assert next_index >= 0
            assert next_index < total
            assert prev_index >= 0
            assert prev_index < total
            self.actionNext.setToolTip(f"{self.actionNext.text()}: {Path(self.image_list[next_index]).name}")
            self.actionPrevious.setToolTip(f"{self.actionPrevious.text()}: {Path(self.image_list[prev_index]).name}")
            self.actionNext.setEnabled(True)
            self.actionPrevious.setEnabled(True)

    @QtCore.Slot(str)  # noqa
    def file_open_event(self, file_: str):
        self.load_main_image(file_)

    # TODO: nuanced QImage format for clipboard
    _qimage_format_for_pil_mode = {
        "RGBA": QtGui.QImage.Format.Format_RGBA8888,
    }

    @QtCore.Slot()  # noqa
    def on_actionCopy_triggered(self):  # noqa
        # TODO - create a separate container for images...
        temp = self.image.convert("RGBA")
        qimage = QtGui.QImage(
            temp.tobytes("raw", "RGBA"),
            temp.size[0],
            temp.size[1],
            QtGui.QImage.Format.Format_RGBA8888,
        )
        self.clipboard.setImage(qimage)

    @QtCore.Slot(bool)  # noqa
    def on_actionEquidistant_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.EQUIDISTANT, self.actionEquidistant)

    @QtCore.Slot(bool)  # noqa
    def on_actionEquirectangular_toggled(self, is_checked: bool):  # noqa
        if is_checked:
            self.set_360_projection(Projection360.EQUIRECTANGULAR, self.actionEquirectangular)

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
            self.set_360_projection(Projection360.GNOMONIC, self.actionPerspective)

    @QtCore.Slot()  # noqa
    def on_actionPaste_triggered(self):  # noqa
        with ScopedWaitCursor():
            clip = ImageGrab.grabclipboard()
            if clip.width < 1:
                self.actionPaste.setEnabled(False)
                return
            file_name = clip.filename
            if file_name is None:
                time_str = time.strftime("%Y%m%d_%H%M%S")
                file_name = f"Clipboard{time_str}"
            if self.load_image_from_memory(image=clip, name=file_name):
                self.undo_stack.resetClean()  # clipboard image has not been saved

    @QtCore.Slot()  # noqa
    def on_actionNext_triggered(self):  # noqa
        if len(self.image_list) < 2:
            self.actionNext.setEnabled(False)
            return
        if self.image_index >= len(self.image_list) - 1:
            box = QMessageBox()
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("Continue from first image?")
            box.setText(cleandoc("""
               This is the final image.
               Do you want to continue from the first image?
            """))
            box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
            box.setDefaultButton(QMessageBox.Yes)
            button_yes = box.button(QMessageBox.Yes)
            button_yes.setText("Continue")
            reply = box.exec()
            if reply != QMessageBox.Yes:
                return
        self.image_index += 1
        if self.image_index >= len(self.image_list):
            self.image_index -= len(self.image_list)
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
        if len(self.image_list) < 2:
            self.actionPrevious.setEnabled(False)
            return
        if self.image_index <= 0:
            box = QMessageBox()
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("Continue from final image?")
            box.setText(cleandoc("""
               This is the first image.
               Do you want to continue from the final image?
            """))
            box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
            box.setDefaultButton(QMessageBox.Yes)
            button_yes = box.button(QMessageBox.Yes)
            button_yes.setText("Continue")
            reply = box.exec()
            if reply != QMessageBox.Yes:
                return
        self.image_index -= 1
        if self.image_index < 0:
            self.image_index += len(self.image_list)
        self.activate_indexed_image()

    @QtCore.Slot()  # noqa
    def on_actionSave_As_triggered(self):  # noqa
        file_path = self._dialog_and_save_image(self.image)
        if os.path.exists(file_path):
            self.set_current_image_path(file_path)
            self.undo_stack.setClean()

    @QtCore.Slot()  # noqa
    def on_actionSave_Current_View_As_triggered(self):  # noqa
        pixmap = self.imageWidgetGL.grab()
        view_image = Image.fromqpixmap(pixmap)
        file_path = self._dialog_and_save_image(view_image)
        if os.path.exists(file_path):
            self.recent_files.add_file(file_path)

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
            self.set_360_projection(Projection360.STEREOGRAPHIC, self.actionStereographic)

    @QtCore.Slot(int)  # noqa
    def projection_combo_box_current_index_changed(self, index: int):
        projection_action = self.projectionComboBox.itemData(index)
        projection_action.trigger()

    @QtCore.Slot(bool)  # noqa
    def undo_stack_clean_changed(self, clean: bool):
        print(clean)
        self.setWindowModified(not clean)
