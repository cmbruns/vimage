import inspect

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
import PIL
from PySide6 import QtOpenGLWidgets
from PySide6.QtCore import Qt


class ImageWidgetGL(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewport = (0, 0, 10, 10)
        self.image: numpy.ndarray = None
        self.setCursor(Qt.CrossCursor)
        self.setMinimumSize(10, 10)
        self.vao = None
        self.shader = None
        self.texture = None
        self.image_needs_upload = False

    def initializeGL(self) -> None:
        # Use native-like background color
        bg_color = self.palette().color(self.backgroundRole()).getRgbF()
        GL.glClearColor(*bg_color)
        # Make transparent images transparent
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.shader = compileProgram(
            compileShader(inspect.cleandoc("""
                #version 410
                
                // host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
                const vec4 SCREEN_QUAD[4] = vec4[4](
                    vec4( 1, -1, 0.5, 1),  // lower right
                    vec4( 1,  1, 0.5, 1),  // upper right
                    vec4(-1, -1, 0.5, 1),  // lower left
                    vec4(-1,  1, 0.5, 1)   // upper left
                );
                
                out vec2 tex_coord;
                
                void main() {
                    gl_Position = SCREEN_QUAD[gl_VertexID];
                    tex_coord = SCREEN_QUAD[gl_VertexID].xy;
                    tex_coord *= vec2(0.5, -0.5);
                    tex_coord += vec2(0.5, 0.5);
                }
            """), GL.GL_VERTEX_SHADER),
            compileShader(inspect.cleandoc("""
                #version 410

                uniform sampler2D image;
                in vec2 tex_coord;
                out vec4 color;
                
                void main() {
                    color = texture(image, tex_coord);
                }
            """), GL.GL_FRAGMENT_SHADER),
        )
        self.texture = GL.glGenTextures(1)

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glBindVertexArray(self.vao)
        if self.image is not None:
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
            if self.image_needs_upload:
                # Number of channels
                formats = {
                    1: GL.GL_RED,
                    3: GL.GL_RGB,
                    4: GL.GL_RGBA,
                }
                channel_count = 1
                if len(self.image.shape) > 2:
                    channel_count = self.image.shape[2]
                # Bit depth
                depths = {
                    numpy.dtype("uint8"): GL.GL_UNSIGNED_BYTE,
                    numpy.dtype("uint16"): GL.GL_UNSIGNED_SHORT,
                }
                h, w = self.image.shape[:2]  # Image dimensions
                GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
                if channel_count == 1:
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
                else:
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_GREEN)
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_BLUE)
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D,
                    0,
                    formats[channel_count],
                    w,
                    h,
                    0,
                    formats[channel_count],
                    depths[self.image.dtype],
                    self.image,
                )
                # TODO: implement toggle between NEAREST, LINEAR, CUBIC...
                GL.glTexParameteri(
                    GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR
                )
                GL.glTexParameteri(
                    GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST
                )
                GL.glTexParameteri(
                    GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE
                )
                GL.glTexParameteri(
                    GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE
                )
                GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
                self.image_needs_upload = False
            GL.glViewport(*self.viewport)
            GL.glUseProgram(self.shader)
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

    def resizeGL(self, width: int, height: int) -> None:
        self.update_viewport()
        self.update()

    def set_image(self, image: PIL.Image.Image):
        self.image = numpy.array(image)
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3] / 255.0
            for rgb in range(3):
                a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
        self.image_needs_upload = True
        self.update_viewport()
        self.update()

    def update_viewport(self):
        """The OpenGL viewport is used to enforce correct display aspect ratio"""
        sh, sw = self.height(), self.width()  # Window shape
        if sh == 0 or sw == 0:
            return
        x, y, width, height = 0, 0, sw, sh  # Default viewport is the entire window
        if self.image is not None:
            ih, iw = self.image.shape[:2]  # Image shape
            if ih > 0 and iw > 0:
                if iw/ih > sw/sh:
                    # image aspect ratio is wider than window, so pad at top and bottom
                    h2 = sw * ih / iw  # used window height
                    y = int(0.5 + (sh - h2) / 2)
                    height = int(0.5 + h2)
                else:
                    # image aspect ratio is taller than window, so pad at left and right
                    w2 = sh * iw / ih  # used window height
                    x = int(0.5 + (sw - w2) / 2)
                    width = int(0.5 + w2)
        self.viewport = (x, y, width, height)
