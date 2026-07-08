import numpy
from OpenGL import GL

from vmg.render_state import RenderStateLike


class DngTextureAdapter:
    """Intended match interface of vmg.Texture"""
    def __init__(self, dng_image: "DngImage"):
        self.dng_image = dng_image
        self._tile_X_img = numpy.eye(3, dtype=numpy.float32)

    def __iter__(self):
        yield self  # Until we have actual tiles

    def __len__(self):
        return 1  # Until we have tiles

    def initialize_gl(self):
        self.dng_image.initialize_gl()

    def is_ready(self) -> bool:
        if self.dng_image.load_sync is None:
            return False
        load_status = GL.glGetSynciv(self.dng_image.load_sync, GL.GL_SYNC_STATUS, 1)[1]
        return load_status == GL.GL_SIGNALED

    def paint_gl(self, state: RenderStateLike) -> bool:
        return self.dng_image.paint_gl(state)

    @property
    def tile_X_img(self):
        return self._tile_X_img
