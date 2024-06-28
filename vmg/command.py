import logging

import pathlib

import PIL.Image
from PySide6.QtGui import QUndoCommand

from vmg.selection_box import (SelectionBox, SelState)

logger = logging.getLogger(__name__)


class CropToSelection(QUndoCommand):
    def __init__(
            self,
            image: PIL.Image.Image,
            rect: SelectionBox,
            window,  # VimageMainWindow
            file_name: str,
    ):
        super().__init__()
        self.setText("Crop to selection")
        self.image = image.copy()
        self.bounds = (
            max(rect.left, 0),
            max(rect.top, 0),
            min(rect.right, image.width),
            min(rect.bottom, image.height),
        )
        self.window = window
        self.file_name = file_name

    def redo(self):
        stem = pathlib.Path(self.file_name).stem
        logger.info(f"Cropping image {stem} to {self.bounds}")
        cropped = self.image.crop(self.bounds)
        name = f"{stem}_cropped"
        self.window.load_image_from_memory(image=cropped, name=name)
        rect = self.window.imageWidgetGL.view_state.sel_rect
        rect.clear()

    def undo(self):
        logger.info(f"Undoing crop image")
        self.window.load_image_from_memory(self.image, self.file_name)
        rect = self.window.imageWidgetGL.view_state.sel_rect
        rect.left = self.bounds[0]
        rect.top = self.bounds[1]
        rect.right = self.bounds[2]
        rect.bottom = self.bounds[3]
        rect.state = SelState.COMPLETE
        self.window.imageWidgetGL.update()
