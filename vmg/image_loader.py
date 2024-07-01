import logging

import turbojpeg
from OpenGL import GL
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import Qt

from vmg.elapsed_time import ElapsedTime
from vmg.image_data import ImageData
from vmg.offscreen_context import OffscreenContext
from vmg.texture import Texture


jpeg = turbojpeg.TurboJPEG()  # TODO: cache this?
logger = logging.getLogger(__name__)


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.current_image_data = None
        # Connect the loading process via a series of signals,
        # so the process can be interrupted when a new file is requested
        self.pil_image_assigned.connect(self.load_metadata, Qt.QueuedConnection)  # noqa
        self.turbo_jpeg_texture_requested.connect(self.texture_turbo_jpeg, Qt.QueuedConnection)  # noqa
        self.pil_texture_requested.connect(self.texture_pil, Qt.QueuedConnection)  # noqa
        self.bytes_loaded.connect(self.process_texture, Qt.QueuedConnection)  # noqa
        self.offscreen_context = None
        self.threaded_texture_feature = True

    load_failed = QtCore.Signal(str)
    pil_image_assigned = QtCore.Signal(ImageData)
    turbo_jpeg_texture_requested = QtCore.Signal(ImageData)
    pil_texture_requested = QtCore.Signal(ImageData)
    bytes_loaded = QtCore.Signal(ImageData)
    texture_created = QtCore.Signal(ImageData)

    @QtCore.Slot(str)  # noqa
    def load_from_file_name(self, file_name: str):
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        if not image_data.file_is_readable():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        et = ElapsedTime()
        if not image_data.open_pil_image():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        logger.info(f"Opening PIL image took {et}")
        self.pil_image_assigned.emit(image_data)  # noqa

    @QtCore.Slot(Image.Image, str)  # noqa
    def load_from_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        image_data.pil_image = pil_image
        self.pil_image_assigned.emit(image_data)  # noqa

    def _is_current(self, image_data: ImageData) -> bool:
        if self.current_image_data is not image_data:
            image_data.setParent(None)  # noqa  allow deletion of image_data maybe
            logger.info(f"ceasing stale load of {image_data.file_name}")
            return False  # Latest file is something else
        else:
            return True

    @QtCore.Slot(ImageData)  # noqa
    def load_metadata(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        et = ElapsedTime()
        assert image_data.pil_image is not None
        if image_data.pil_image.width < 1 or image_data.pil_image.height < 1:
            self.load_failed.emit(file_name)  # noqa
            return
        image_data.read_pil_metadata()
        logger.info(f"Loading metadata took {et}")
        if image_data.pil_image.format == "JPEG" and image_data.file_is_readable():
            self.turbo_jpeg_texture_requested.emit(image_data)  # noqa
        else:
            self.pil_texture_requested.emit(image_data)  # noqa

    @QtCore.Slot(OffscreenContext)  # noqa
    def on_context_created(self, offscreen_context) -> None:
        logger.info("OpenGL context created")
        assert self.offscreen_context is None
        self.offscreen_context = offscreen_context
        self.offscreen_context.moveToThread(self.thread())

    @QtCore.Slot(ImageData)  # noqa
    def texture_turbo_jpeg(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        assert image_data.file_name is not None
        et = ElapsedTime()
        with open(image_data.file_name, "rb") as in_file:
            jpeg_bytes = in_file.read()
        bgr_array = jpeg.decode(jpeg_bytes)
        image_data.texture = Texture.from_numpy(array=bgr_array, tex_format=GL.GL_BGR)
        logger.info(f"jpeg loading/decoding took {et}")
        if self.offscreen_context is None:
            self.texture_created.emit(image_data)  # noqa
        else:
            self.bytes_loaded.emit(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def texture_pil(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        et = ElapsedTime()
        img = image_data.pil_image
        assert img is not None
        if img.mode in ["P",]:
            image_data.pil_image = image_data.pil_image.convert("RGBA")  # TODO: palette shader
            img = image_data.pil_image
            channel_count = 4
        elif img.mode in ["1", "L", "I", "I;16", "I;16L", "I;16B", "I;16N", "F"]:
            channel_count = 1
        elif img.mode in ["LA", "La", "PA"]:
            channel_count = 2
        elif img.mode in ["RGB", "CMYK", "YCbCr", "LAB", "HSV", "BGR;15", "BGR;16", "BGR;24"]:
            channel_count = 3
        elif img.mode in ["RGBA", "RGBa"]:
            channel_count = 4
        else:
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        data = img.tobytes()
        image_data.texture = Texture(
            channel_count=channel_count,
            size=img.size,
            data_type=GL.GL_UNSIGNED_BYTE,  # TODO...
            data=data,
            # tex_format=?,  # TODO:
        )
        logger.info(f"PIL image processing took {et}")
        if self.offscreen_context is None:
            self.texture_created.emit(image_data)  # noqa
        else:
            self.bytes_loaded.emit(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def process_texture(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        if self.threaded_texture_feature:
            # Upload the texture in the image loading thread, using
            # our shared OpenGL context
            et = ElapsedTime()
            with self.offscreen_context:
                image_data.texture.bind_gl()
                # Make sure texture is fully uploaded before switching to another QThread
                GL.glFinish()  # glFinish blocks, glFlush does not
                logger.info(f"(Loading thread) texture upload took {et}")
        self.texture_created.emit(image_data)  # noqa
