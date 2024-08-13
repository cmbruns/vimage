"""
Minimal image viewing example, as basis for testing deconstruction. Aug 8, 2024
"""

from ctypes import c_float, c_void_p, cast, sizeof
import inspect
import sys
import time

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
from PySide6 import QtCore
from PySide6.QtCore import QObject, QThread, Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QOffscreenSurface, QOpenGLContext
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication


Image.MAX_IMAGE_PIXELS = 2000120000


class MyFileWrapper(object):
    """Maybe track file load progress"""
    def __init__(self, file_stream):
        self.file_stream = file_stream

    def read(self, val: int):
        return self.file_stream.read(val)

    def seek(self, val: int):
        self.file_stream.seek(val)


class MyGLContext(object):
    def __init__(self, parent_gl_context, gl_format):
        self.parent_context = parent_gl_context
        self.gl_format = gl_format
        self.context = None
        self.surface = None
        self.max_texture_size = None

    def __enter__(self):
        if self.context is None:
            self.surface = QOffscreenSurface()
            self.surface.setFormat(self.gl_format)
            self.surface.create()
            assert self.surface.isValid()
            self.context = QOpenGLContext()
            self.context.setShareContext(self.parent_context)
            self.context.setFormat(self.surface.requestedFormat())
            self.context.create()
            assert self.context.isValid()
        self.context.makeCurrent(self.surface)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.context.doneCurrent()


class Tile(object):
    def __init__(self, image, left, top, width, height):
        self.vao = None
        self.vbo = None
        # Convert to normalized image coordinates
        left_nic = 2 * left / image.width - 1
        right_nic = 2 * (left + width) / image.width - 1
        top_nic = 1 - 2 * top / image.height
        bottom_nic = 1 - 2 * (top + height) / image.height
        self.vertexes = numpy.array(
            [
                # nic_x, nic_y, txc_x, txc_y
                [left_nic, top_nic, 0, 0],  # upper left
                [left_nic, bottom_nic, 0, 1],  # lower left
                [right_nic, top_nic, 1, 0],  # upper right
                [right_nic, bottom_nic, 1, 1],  # lower right
            ],
            dtype=numpy.float32
        ).flatten()
        self.texture_id = None
        self.load_sync = None
        self.image = image
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    def initialize_gl(self):
        self.vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, len(self.vertexes) * sizeof(c_float), self.vertexes, GL.GL_STATIC_DRAW)
        self.texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        # row stride required for horizontal tiling
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, self.image.width)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, self.left)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, self.top)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGB,
            self.width,
            self.height,
            0,
            GL.GL_RGB,
            GL.GL_UNSIGNED_BYTE,
            self.image.tobytes(),
        )
        # Restore normal unpack settings
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, 0)
        self.load_sync = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)

    def is_ready(self) -> bool:
        load_status = GL.glGetSynciv(self.load_sync, GL.GL_SYNC_STATUS, 1)[1]
        return load_status == GL.GL_SIGNALED

    def paint_gl(self):
        if not self.is_ready():
            return
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        # VAO must be created here, in the render thread
        if self.vao is None:
            self.vao = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(self.vao)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
            f_size = sizeof(c_float)
            GL.glVertexAttribPointer(  # normalized image coordinates
                1,  # attribute index
                2,  # size (#components)
                GL.GL_FLOAT,  # type
                False,  # normalized
                f_size * 4,  # stride (bytes)
                cast(0 * f_size, c_void_p),  # pointer offset
            )
            GL.glEnableVertexAttribArray(1)
            GL.glVertexAttribPointer(  # texture coordinates
                2,  # attribute index
                2,  # size (#components)
                GL.GL_FLOAT,  # type
                False,  # normalized
                f_size * 4,  # stride (bytes)
                cast(2 * f_size, c_void_p),  # pointer offset
            )
            GL.glEnableVertexAttribArray(2)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


class Texture(QObject):
    def __init__(self, image_file_name: str):
        super().__init__()
        with open(image_file_name, "rb") as img:
            # TODO: modular loading: PIL, jpeg turbo, ctjpeg, etc
            pil = Image.open(MyFileWrapper(img))
            pil.load()
        self.image = pil
        self.tiles = []

    def __getitem__(self, key):
        return self.tiles[key]

    def __len__(self):
        return len(self.tiles)

    def initialize_gl(self):
        max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)
        if self.image.width > max_texture_size or self.image.height > max_texture_size:
            tile_size = 8192
            assert tile_size < max_texture_size
            top = 0
            while top <= self.image.height:
                left = 0
                while left <= self.image.width:
                    width = min(tile_size, self.image.width - left)
                    height = min(tile_size, self.image.height - top)
                    print(left, top, width, height)
                    self.tiles.append(Tile(self.image, left, top, width, height))
                    left += tile_size
                top += tile_size
        else:
            self.tiles.append(Tile(self.image, 0, 0, self.image.width, self.image.height))  # just one tile needed
        for tile in self.tiles:
            tile.initialize_gl()

    def paint_gl(self):
        for tile in self:
            tile.paint_gl()


class ImageLoader(QObject):
    def __init__(self, parent_gl_context, gl_format):
        super().__init__()
        self.parent_context = parent_gl_context
        self.gl_format = gl_format
        self.texture = None
        self.context = MyGLContext(parent_gl_context, gl_format)
        self._load_canceled = False

    def _loaded_tile_count(self) -> int:
        loaded_tile_count = 0
        with self.context:
            for tile in self.texture:
                if tile.is_ready():
                    loaded_tile_count += 1
        return loaded_tile_count

    def _check_cancel(self) -> bool:
        QCoreApplication.processEvents()  # In case load was canceled
        return self._load_canceled

    image_size_changed = QtCore.Signal(int, int)

    @QtCore.Slot(str)  # noqa
    def load_image(self, image_file_name: str):
        print("ImageLoader.load_image()")
        self._load_canceled = False
        self.texture = Texture(image_file_name)
        self.image_size_changed.emit(*self.texture.image.size)  # noqa
        if self._check_cancel():
            return
        with self.context:
            self.texture.initialize_gl()
            if self._check_cancel():
                return
        previous_num_loaded_tiles = 0
        num_loaded_tiles = self._loaded_tile_count()
        while num_loaded_tiles < len(self.texture):
            print("waiting for tile upload")
            time.sleep(0.050)
            if self._check_cancel():
                return
            num_loaded_tiles = self._loaded_tile_count()
        print("ImageLoader.texture_loaded()")
        self.texture_loaded.emit(self.texture)

    texture_loaded = QtCore.Signal(Texture)


class RenderWindow(QOpenGLWidget):
    def __init__(self, image_file_name):
        super().__init__()
        self.image_file_name = image_file_name
        self.resize(640, 480)
        self.image_loader = None
        self.loading_thread = QThread()
        self.shader = None
        self.texture = None

    def initializeGL(self):
        GL.glClearColor(0, 0, 1, 1)
        self.shader = compileProgram(
            compileShader(inspect.cleandoc("""
                #version 410

                layout(location = 1) in vec2 pos_nic;  // normalized image coordinates
                layout(location = 2) in vec2 pos_txc;  // texture coordinates

                out vec2 texCoord;

                void main() {
                    gl_Position = vec4(pos_nic, 0.5, 1);
                    texCoord = pos_txc;
                }
            """), GL.GL_VERTEX_SHADER),
            compileShader(inspect.cleandoc("""
                #version 410

                uniform sampler2D image;
                in vec2 texCoord;
                out vec4 color;

                void main() {
                    color = texture(image, texCoord);
                }
            """), GL.GL_FRAGMENT_SHADER),
        )
        self.image_loader = ImageLoader(self.context(), self.format())
        self.image_loader.moveToThread(self.loading_thread)
        self.loading_thread.start()
        self.request_image.connect(self.image_loader.load_image, Qt.QueuedConnection)
        self.image_loader.texture_loaded.connect(self.set_texture, Qt.QueuedConnection)
        self.image_loader.image_size_changed.connect(self.update_image_size, Qt.QueuedConnection)  # noqa
        self.request_image.emit(self.image_file_name)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.texture is not None:
            GL.glUseProgram(self.shader)
            self.texture.paint_gl()
        else:
            print("Texture not loaded yet")

    request_image = QtCore.Signal(str)

    def set_texture(self, texture):
        print("RenderWindow.setTexture()")
        self.texture = texture
        self.update()

    def update_image_size(self, width, height):
        w, h = width, height
        mx = max(width, height)
        if mx > 256:
            scale = 256 / mx
            w = int(scale * width)
            h = int(scale * height)
        self.resize(w, h)


def main():
    f = QSurfaceFormat()
    f.setProfile(QSurfaceFormat.CoreProfile)
    f.setVersion(4, 1)
    QSurfaceFormat.setDefaultFormat(f)
    app = QApplication(sys.argv)
    window = RenderWindow(
        # "../test/images/Grace_Hopper.jpg"
        "C:/Users/cmbruns/Pictures/_Bundles_for_Berlin__More_production!.jpg"
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
