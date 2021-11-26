from PIL import Image, ImageQt
from PySide6 import QtGui, QtWidgets


class ImageWidget(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap = None
        self.adjusted_to_size = (-1, -1)
        self.ratio = 1.0

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        size = event.size()
        self.update_margins(size)

    def set_image(self, image: Image.Image):
        self.pixmap = QtGui.QPixmap.fromImage(ImageQt.ImageQt(image))
        self.setPixmap(self.pixmap)
        self.setMinimumSize(10, 10)
        self.ratio = self.pixmap.width() / self.pixmap.height()
        self.adjusted_to_size = (-1, -1)
        self.update_margins(self.size())
        self.update()

    def update_margins(self, size):
        if size == self.adjusted_to_size:
            return
        full_width = size.width()
        full_height = size.height()
        width = min(full_width, full_height * self.ratio)
        height = min(full_height, full_width / self.ratio)
        h_margin = round((full_width - width) / 2)
        v_margin = round((full_height - height) / 2)
        self.adjusted_to_size = size
        self.setContentsMargins(h_margin, v_margin, h_margin, v_margin)
