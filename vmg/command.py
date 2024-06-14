import PIL.Image
from PySide6.QtGui import QUndoCommand

from vmg.rect_sel import RectangularSelection, SelState


class CropToSelection(QUndoCommand):
    def __init__(
            self,
            image: PIL.Image.Image,
            rect: RectangularSelection,
            window,  # VimageMainWindow
            file_name: str,
    ):
        super().__init__()
        self.setText("Crop to selection")
        self.image = image.copy()
        self.bounds = (rect.left, rect.top, rect.right, rect.bottom)
        self.window = window
        self.file_name = file_name

    def redo(self):
        cropped = self.image.crop(self.bounds)
        if self.window.load_image_from_memory(image=cropped, name="Cropped"):
            rect = self.window.imageWidgetGL.view_state.sel_rect
            rect.clear()

    def undo(self):
        print("undo")
        self.window.load_image_from_memory(self.image, self.file_name)
        rect = self.window.imageWidgetGL.view_state.sel_rect
        rect.left = self.bounds[0]
        rect.top = self.bounds[1]
        rect.right = self.bounds[2]
        rect.bottom = self.bounds[3]
        rect.state = SelState.COMPLETE
        self.window.imageWidgetGL.update()
