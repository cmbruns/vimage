import logging
import time

import turbojpeg
from OpenGL import GL
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication

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
        self.offscreen_context = None

    load_failed = QtCore.Signal(str)
    texture_created = QtCore.Signal(ImageData)

    @QtCore.Slot(str)  # noqa
    def cancel_load(self):
        if self.current_image_data is None:
            return  # already canceled?
        self.current_image_data = None

    def _is_current(self, image_data: ImageData) -> bool:
        QCoreApplication.processEvents()  # drain queue, in case load was canceled
        if self.current_image_data is not image_data:
            image_data.setParent(None)  # noqa  allow deletion of image_data maybe
            logger.info(f"ceasing stale load of {image_data.file_name}")
            return False  # Latest file is something else
        else:
            return True

    @QtCore.Slot(str)  # noqa
    def load_from_file_name(self, file_name: str):
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        if not self._is_current(image_data):
            return
        if not image_data.file_is_readable():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        self.progress_changed.emit(2)  # noqa
        et = ElapsedTime()
        if not image_data.open_pil_image():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        logger.info(f"Opening PIL image took {et}")
        self.load_metadata(image_data)

    @QtCore.Slot(Image.Image, str)  # noqa
    def load_from_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image_data = ImageData(file_name, parent=self)
        self.current_image_data = image_data
        self.progress_changed.emit(5)  # noqa
        image_data.pil_image = pil_image
        self.load_metadata(image_data)

    def load_metadata(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        et = ElapsedTime()
        assert image_data.pil_image is not None
        if image_data.pil_image.width < 1 or image_data.pil_image.height < 1:
            self.load_failed.emit(file_name)  # noqa
            return
        self.progress_changed.emit(10)  # noqa
        image_data.read_pil_metadata()
        logger.info(f"Loading metadata took {et}")
        if image_data.pil_image.format == "JPEG" and image_data.file_is_readable():
            self.texture_turbo_jpeg(image_data)
        else:
            self.texture_pil(image_data)  # noqa

    @QtCore.Slot(OffscreenContext)  # noqa
    def on_context_created(self, offscreen_context) -> None:
        logger.info("OpenGL context created")
        assert self.offscreen_context is None
        self.offscreen_context = offscreen_context

    @QtCore.Slot(ImageData)  # noqa
    def texture_turbo_jpeg(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        assert image_data.file_name is not None
        self.progress_changed.emit(15)  # noqa
        et = ElapsedTime()
        with open(image_data.file_name, "rb") as in_file:
            jpeg_bytes = in_file.read()
        bgr_array = jpeg.decode(jpeg_bytes)
        image_data.texture = Texture.from_numpy(
            array=bgr_array,
            tex_format=GL.GL_BGR,
            orientation=image_data.orientation,
        )
        logger.info(f"jpeg loading/decoding took {et}")
        if self.offscreen_context is None:
            self.texture_created.emit(image_data)  # noqa
        else:
            self.process_texture(image_data)  # noqa

    @QtCore.Slot(ImageData)  # noqa
    def texture_pil(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        et = ElapsedTime()
        img = image_data.pil_image
        assert img is not None
        self.progress_changed.emit(15)  # noqa
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
            orientation=image_data.orientation,
        )
        logger.info(f"PIL image processing took {et}")
        if self.offscreen_context is None:
            self.texture_created.emit(image_data)  # noqa
        else:
            self.process_texture(image_data)  # noqa

    def _loaded_tile_count(self, image_data) -> int:
        loaded_tile_count = 0
        with self.offscreen_context:
            for tile in image_data.texture:
                if tile.is_ready():
                    loaded_tile_count += 1
        return loaded_tile_count

    @QtCore.Slot(ImageData)  # noqa
    def process_texture(self, image_data: ImageData):
        if not self._is_current(image_data):
            return
        self.progress_changed.emit(60)  # noqa
        # Upload the texture in the image loading thread, using
        # our shared OpenGL context
        et = ElapsedTime()
        with self.offscreen_context:
            image_data.texture.initialize_gl()
            if not self._is_current(image_data):
                return
            num_loaded_tiles = self._loaded_tile_count(image_data)
            while num_loaded_tiles < len(image_data.texture):
                print("waiting for tile upload")  # TODO: logging
                time.sleep(0.050)
                if not self._is_current(image_data):
                    return
                num_loaded_tiles = self._loaded_tile_count(image_data)
            print("ImageLoader.texture_loaded()")  # TODO: logging
            # self.texture_changed.emit(image_data.texture)  # noqa
            logger.info(f"(Loading thread) tile upload took {et}")
            self.progress_changed.emit(90)
        self.texture_created.emit(image_data)  # noqa

    progress_changed = QtCore.Signal(int)
