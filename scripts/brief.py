"""
Minimal image viewing example, as basis for testing deconstruction. Aug 8, 2024
"""

import inspect
import sys

from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication


class Texture(object):
    def __init__(self, image):
        self.image = image
        self.texture_id = None
        self.load_sync = None

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

    def is_loaded(self) -> bool:
        load_status = GL.glGetSynciv(self.load_sync, GL.GL_SYNC_STATUS, 1)[1]
        return load_status == GL.GL_SIGNALED


class RenderWindow(QOpenGLWidget):
    def __init__(self, image):
        super().__init__()
        self.resize(image.width, image.height)
        self.texture = Texture(image)
        self.vao = None
        self.shader = None

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
        self.texture.initialize_gl()

    def paintGL(self):
        if self.texture.is_loaded():
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glBindVertexArray(self.vao)
            GL.glUseProgram(self.shader)
            self.texture.bind()
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
        else:
            self.update()


def main():
    f = QSurfaceFormat()
    f.setProfile(QSurfaceFormat.CoreProfile)
    f.setVersion(4, 1)
    QSurfaceFormat.setDefaultFormat(f)
    app = QApplication(sys.argv)
    with open("../test/images/Grace_Hopper.jpg", "rb") as img:
        pil = Image.open(img)
        pil.load()
    window = RenderWindow(pil)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
