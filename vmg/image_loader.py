
import logging
import time
from typing import Optional

import turbojpeg
from OpenGL import GL
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication

from vmg.elapsed_time import ElapsedTime
from vmg.interfaces import ImageLike
from vmg.offscreen_context import OffscreenContext
from vmg.image_like import ImageLikeNew, PilImage, InappropriateImageLoader, DngImage, LoadProgress
from vmg.texture import Texture


jpeg = turbojpeg.TurboJPEG()  # TODO: cache this?
logger = logging.getLogger(__name__)


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.current_image: Optional[ImageLike] = None
        self.offscreen_context = None
        self.image_data_is_pending = False

    load_failed = QtCore.Signal(str)
    texture_created = QtCore.Signal(ImageLike)

    @QtCore.Slot(str)  # noqa
    def cancel_load(self):
        if self.current_image is None:
            return  # already canceled?
        self.current_image = None

    def _is_current(self, image: ImageLike) -> bool:
        QCoreApplication.processEvents()  # drain queue, in case load was canceled
        if self.current_image is not image:
            try:
                image.setParent(None)  # noqa  allow deletion of image maybe
            except AttributeError:
                pass
            logger.info(f"ceasing stale load of {image.file_name}")
            return False  # Latest file is something else
        else:
            return True

    @QtCore.Slot(str)  # noqa
    def load_from_file_name(self, file_name: str):
        use_new = True
        if use_new:
            image = ImageLikeNew()
            image.sq.image_displayed.connect(self.on_image_displayed)
            image.sq.progress_changed.connect(self.on_progress_changed)
            image.set_progress(LoadProgress.OBJECT_CREATED)
            if not image.load_from_file(file_name):
                self.load_failed.emit(file_name)
                return
        else:
            # TODO: Try various image loaders
            image = None
            for image_class in [DngImage, PilImage]:
                try:
                    image = image_class(file_name)
                    break
                except InappropriateImageLoader:
                    continue
        if image is None:
            self.load_failed.emit(file_name)
            return
        self.current_image = image
        if self.offscreen_context is None:
            self.image_data_is_pending = True
            logger.debug(
                f"Deferring texture initialization for {image.md.file_name} until OpenGL context is ready"
            )
        else:
            self.upload_image(image)  # noqa

    @QtCore.Slot(Image.Image, str)  # noqa
    def load_from_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image = ImageLikeNew()
        image.sq.image_displayed.connect(self.on_image_displayed)
        image.sq.progress_changed.connect(self.on_progress_changed)
        image.set_progress(LoadProgress.OBJECT_CREATED)
        image.load_from_pil_image(pil_image, file_name)
        self.current_image = image
        if self.offscreen_context is None:
            self.image_data_is_pending = True
            logger.debug(
                f"Deferring texture initialization for {image.md.file_name} until OpenGL context is ready"
            )
        else:
            self.upload_image(image)  # noqa

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
        if not self._is_current(image_data):
            return
        if self.texture_turbo_jpeg(image_data):
            pass
        elif self.texture_pil(image_data):
            logger.info("texture_pil")
            pass
        elif self.texture_dng(image_data):
            logger.info("texture_dng")
            pass
        else:
            return  # Nothing loaded
        if self.offscreen_context is None:
            self.image_data_is_pending = True
            logger.debug(
                f"Deferring texture initialization for {image_data.file_name} until OpenGL context is ready"
            )
        else:
            self.process_texture(image_data)  # noqa

    @QtCore.Slot(OffscreenContext)  # noqa
    def on_context_created(self, offscreen_context) -> None:
        logger.info("Received new opengl context.")
        # logger.info(f"{self.pending_image_data}, {self.current_image_data}")
        assert self.offscreen_context is None
        self.offscreen_context = offscreen_context
        if self.image_data_is_pending:
            logger.debug("Uploading pending image data")
            self.image_data_is_pending = False
            logger.debug("about to create context")
            self.upload_image(self.current_image)

    @QtCore.Slot(ImageLike)  # noqa
    def texture_turbo_jpeg(self, image_data: ImageLike) -> bool:
        if not image_data.pil_image.format == "JPEG":
            return False
        if not image_data.file_is_readable():
            return False
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
        image_data.texture.texture_displayed.connect(self.on_texture_displayed)
        return True

    def _loaded_tile_count(self, image: ImageLike) -> int:
        """Count ready tiles; offscreen context must already be current."""
        loaded_tile_count = 0
        for tile in image.tiles:
            if tile.is_ready():
                loaded_tile_count += 1
        return loaded_tile_count

    @QtCore.Slot(ImageLike)  # noqa
    def on_image_displayed(self, image: ImageLike):
        if image is self.current_image:
            self.image_displayed.emit(self.current_image)

    @QtCore.Slot(Texture)  # noqa
    def on_progress_changed(self, progress: int, image: ImageLike):
        if image is self.current_image:
            self.progress_changed.emit(progress)

    def upload_image(self, image: ImageLike):
        if not self._is_current(image):
            return
        with self.offscreen_context:
            image.initialize_gl()
            if not self._is_current(image):
                return
            num_loaded_tiles = self._loaded_tile_count(image)
            n_tiles = len(list(image.tiles))
            while num_loaded_tiles < n_tiles:
                logger.debug("waiting for tile upload")
                time.sleep(0.050)
                if not self._is_current(image):
                    logger.debug("image data is not current")
                    return
                num_loaded_tiles = self._loaded_tile_count(image)
            self.progress_changed.emit(90)  # noqa
            assert image.md.file_name is not None
            self.texture_created.emit(image)  # noqa

    progress_changed = QtCore.Signal(int)
    image_displayed = QtCore.Signal(ImageLike)
