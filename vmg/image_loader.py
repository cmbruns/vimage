import turbojpeg
from OpenGL import GL
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import Qt

from vmg.image_data import ImageData
from vmg.texture import Texture


jpeg = turbojpeg.TurboJPEG()  # TODO: cache this?


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.current_image_data = None
        # Connect the loading process via a series of signals,
        # so the process can be interrupted when a new file is requested
        self.pil_image_assigned.connect(self.load_metadata, Qt.QueuedConnection)  # noqa
        self.turbo_jpeg_texture_requested.connect(self.texture_turbo_jpeg, Qt.QueuedConnection)  # noqa
        self.pil_texture_requested.connect(self.texture_pil, Qt.QueuedConnection)  # noqa

    load_failed = QtCore.Signal(str)
    pil_image_assigned = QtCore.Signal(ImageData)
    turbo_jpeg_texture_requested = QtCore.Signal(ImageData)
    pil_texture_requested = QtCore.Signal(ImageData)
    texture_created = QtCore.Signal(ImageData)

    @QtCore.Slot(str)  # noqa
    def load_from_file_name(self, file_name: str):
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        if not image_data.file_is_readable():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        if not image_data.open_pil_image():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        self.pil_image_assigned.emit(image_data)  # noqa

    @QtCore.Slot(Image.Image, str)  # noqa
    def load_from_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        image_data.pil_image = pil_image
        self.pil_image_assigned.emit(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def load_metadata(self, image_data: ImageData):
        if self.current_image_data is not image_data:
            image_data.setParent(None)  # noqa
            return  # Latest file is something else
        assert image_data.pil_image is not None
        if image_data.pil_image.width < 1 or image_data.pil_image.height < 1:
            self.load_failed.emit(file_name)  # noqa
            return
        image_data.read_pil_metadata()
        if image_data.pil_image.format == "JPEG" and image_data.file_is_readable():
            self.turbo_jpeg_texture_requested.emit(image_data)  # noqa
        else:
            self.pil_texture_requested.emit(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def texture_turbo_jpeg(self, image_data: ImageData):
        if self.current_image_data is not image_data:
            image_data.setParent(None)  # noqa
            return  # Latest file is something else
        assert image_data.file_name is not None
        with open(image_data.file_name, "rb") as in_file:
            jpeg_bytes = in_file.read()
        bgr_array = jpeg.decode(jpeg_bytes)
        image_data.texture = Texture.from_numpy(array=bgr_array, tex_format=GL.GL_BGR)
        self.texture_created.emit(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def texture_pil(self, image_data: ImageData):
        if self.current_image_data is not image_data:
            image_data.setParent(None)  # noqa
            return  # Latest file is something else
        img = image_data.pil_image
        assert img is not None
        data = img.tobytes()
        if img.mode in ["RGB",]:
            channel_count = 3
        else:
            assert False
        image_data.texture = Texture(
            channel_count=channel_count,
            size=img.size,
            data_type=GL.GL_UNSIGNED_BYTE,  # TODO...
            data=data,
            # tex_format=?,  # TODO:
        )
        self.texture_created.emit(image_data)  # noqa
