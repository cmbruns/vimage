import logging
import time
from typing import Optional

import turbojpeg
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication

from vmg.interfaces import TiledImageLike
from vmg.offscreen_context import OffscreenContext
from vmg.tiled_image import TiledImage
from vmg.load_progress import LoadProgress


jpeg = turbojpeg.TurboJPEG()  # TODO: cache this?
logger = logging.getLogger(__name__)


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.current_image: Optional[TiledImageLike] = None
        self.offscreen_context = None
        self.image_data_is_pending = False

    load_failed = QtCore.Signal(str)
    texture_created = QtCore.Signal(TiledImageLike)

    @QtCore.Slot(str)  # noqa
    def cancel_load(self):
        if self.current_image is None:
            return  # already canceled?
        self.current_image = None

    def _is_current(self, image: TiledImageLike) -> bool:
        QCoreApplication.processEvents()  # drain queue, in case load was canceled
        if self.current_image is not image:
            try:
                image.setParent(None)  # noqa  allow deletion of image maybe
            except AttributeError:
                pass
            logger.info(f"ceasing stale load of {image.md.file_name}")
            return False  # Latest file is something else
        else:
            return True

    @QtCore.Slot(str)  # noqa
    def load_from_file_name(self, file_name: str):
        try:
            image = TiledImage()
            image.sq.image_displayed.connect(self.on_image_displayed)
            image.sq.progress_changed.connect(self.on_progress_changed)
            image.set_progress(LoadProgress.OBJECT_CREATED)
            if not image.load_from_file(file_name):
                self.load_failed.emit(file_name)  # noqa
                return
            if image is None:
                self.load_failed.emit(file_name)  # noqa
                return
            self.current_image = image
            if self.offscreen_context is None:
                self.image_data_is_pending = True
                logger.debug(
                    f"Deferring texture initialization for {image.md.file_name} until OpenGL context is ready"
                )
            else:
                self.upload_image(image)  # noqa
        except BaseException as exc:
            logger.error(exc)
            self.load_failed.emit(file_name)

    @QtCore.Slot(Image.Image, str)  # noqa
    def load_from_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image = TiledImage()
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

    @QtCore.Slot(OffscreenContext)  # noqa
    def on_context_created(self, offscreen_context) -> None:
        logger.info("Received new OpenGL context.")
        # logger.info(f"{self.pending_image_data}, {self.current_image_data}")
        assert self.offscreen_context is None
        self.offscreen_context = offscreen_context
        if self.image_data_is_pending:
            logger.debug("Uploading pending image data")
            self.image_data_is_pending = False
            logger.debug("about to create context")
            if self.current_image is not None:
                self.upload_image(self.current_image)

    @staticmethod
    def _loaded_tile_count(image: TiledImageLike) -> int:
        """Count ready tiles; offscreen context must already be current."""
        loaded_tile_count = 0
        for tile in image.tiles:
            if tile.is_ready():
                loaded_tile_count += 1
        return loaded_tile_count

    @QtCore.Slot(TiledImageLike)  # noqa
    def on_image_displayed(self, image: TiledImageLike):
        if image is self.current_image:
            self.image_displayed.emit(self.current_image)  # noqa

    @QtCore.Slot(int, TiledImageLike)  # noqa
    def on_progress_changed(self, progress: int, image: TiledImageLike):
        if image is self.current_image:
            self.progress_changed.emit(progress)  # noqa
            QCoreApplication.processEvents()

    def upload_image(self, image: TiledImageLike):
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
    image_displayed = QtCore.Signal(TiledImageLike)
