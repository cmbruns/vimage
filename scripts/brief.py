"""
Minimal image viewing example, as basis for testing deconstruction. Aug 8, 2024
"""

import inspect
import sys
import time

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
            self.max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)
        self.context.makeCurrent(self.surface)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.context.doneCurrent()


class Tile(object):
    def __init__(self, image):
        self.texture_id = None
        self.load_sync = None
        self.image = image

    def bind(self):
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)

    def initialize_gl(self):
        self.texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGB,
            self.image.width,
            self.image.height,
            0,
            GL.GL_RGB,
            GL.GL_UNSIGNED_BYTE,
            self.image.tobytes(),
        )
        self.load_sync = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)

    def is_ready(self) -> bool:
        load_status = GL.glGetSynciv(self.load_sync, GL.GL_SYNC_STATUS, 1)[1]
        return load_status == GL.GL_SIGNALED


class Texture(object):
    def __init__(self, image_file_name: str):
        with open(image_file_name, "rb") as img:
            pil = Image.open(MyFileWrapper(img))
            pil.load()
        self.image = pil
        self.tiles = []

    def __getitem__(self, key):
        return self.tiles[key]

    def __len__(self):
        return len(self.tiles)

    def initialize_gl(self):
        self.tiles.append(Tile(self.image))  # TODO: more tiles
        for tile in self.tiles:
            tile.initialize_gl()


class ImageLoader(QObject):
    def __init__(self, parent, parent_gl_context, gl_format):
        super().__init__(parent)
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
            loaded_tile_count = 0
            for tile in self.texture:
                if tile.is_ready():
                    loaded_tile_count += 1
        while self._loaded_tile_count() < len(self.texture):
            print("waiting for tile upload")
            time.sleep(0.050)
            if self._check_cancel():
                return
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
        self.vao = None
        self.shader = None
        self.texture = None

    def initializeGL(self):
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        GL.glClearColor(0, 0, 1, 1)
        self.shader = compileProgram(
            compileShader(inspect.cleandoc("""
                #version 410

                const vec4 SCREEN_QUAD_NDC[4] = vec4[4](
                    vec4( 1, -1, 0.5, 1),  // lower right
                    vec4( 1,  1, 0.5, 1),  // upper right
                    vec4(-1, -1, 0.5, 1),  // lower left
                    vec4(-1,  1, 0.5, 1)   // upper left
                );
                out vec2 texCoord;

                void main() {
                    gl_Position = SCREEN_QUAD_NDC[gl_VertexID];
                    texCoord = gl_Position.xy * vec2(0.5, -0.5) + vec2(0.5, 0.5);
                }
            """), GL.GL_VERTEX_SHADER),
            compileShader(inspect.cleandoc("""
                #version 410

                uniform sampler2D image;
                in vec2 texCoord;
                out vec4 color;

                void main() {
                    color = vec4(1, 0, 0, 1);
                    color = texture(image, texCoord);
                }
            """), GL.GL_FRAGMENT_SHADER),
        )
        self.image_loader = ImageLoader(self, self.context(), self.format())
        self.image_loader.moveToThread(self.loading_thread)
        self.request_image.connect(self.image_loader.load_image, Qt.QueuedConnection)
        self.image_loader.texture_loaded.connect(self.set_texture, Qt.QueuedConnection)
        self.image_loader.image_size_changed.connect(self.update_image_size, Qt.QueuedConnection)  # noqa
        self.request_image.emit(self.image_file_name)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.texture is not None:
            GL.glBindVertexArray(self.vao)
            GL.glUseProgram(self.shader)
            for tile in self.texture:
                if tile.is_ready():
                    tile.bind()
                    GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
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
        "../test/images/Grace_Hopper.jpg"
        # r"C:\Users\cmbruns\Pictures\_Bundles_for_Berlin__More_production!.jpg"
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
