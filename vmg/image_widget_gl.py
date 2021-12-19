import pkg_resources

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
import PIL
from PySide6 import QtGui, QtOpenGLWidgets
from PySide6.QtCore import Qt


class ImageWidgetGL(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image: numpy.ndarray = None
        self.setCursor(Qt.CrossCursor)
        self.setMinimumSize(10, 10)
        self.vao = None
        self.shader = None
        self.texture = None
        self.image_needs_upload = False
        self.window_zoom = 1.0
        self.zoom_location = None
        self.window_size_location = None
        self.image_center = [0.5, 0.5]
        self.image_center_location = None
        self.is_dragging = False
        self.previous_mouse_position = None

    def initializeGL(self) -> None:
        # Use native-like background color
        bg_color = self.palette().color(self.backgroundRole()).getRgbF()
        GL.glClearColor(*bg_color)
        # Make transparent images transparent
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        vertex_shader = compileShader(pkg_resources.resource_string(
            "vmg", "image.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(pkg_resources.resource_string(
            "vmg", "image.frag", ), GL.GL_FRAGMENT_SHADER)
        self.shader = compileProgram(vertex_shader, fragment_shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.image_center_location = GL.glGetUniformLocation(self.shader, "image_center")
        #
        self.texture = GL.glGenTextures(1)

    def mouseMoveEvent(self, event):
        if not self.is_dragging:
            return
        if self.image is None:
            return
        # Drag image around
        dx = event.pos().x() - self.previous_mouse_position.x()
        dy = event.pos().y() - self.previous_mouse_position.y()
        x_scale = -self.width() * self.window_zoom
        y_scale = -self.height() * self.window_zoom
        ratio_ratio = self.width() * self.image.shape[0] / (self.height() * self.image.shape[1])
        if ratio_ratio > 1:
            x_scale /= ratio_ratio
        else:
            y_scale *= ratio_ratio
        # Keep the center point on the actual image itself
        self.image_center[0] += dx / x_scale
        self.image_center[1] += dy / y_scale
        self.image_center[0] = max(0, self.image_center[0])
        self.image_center[1] = max(0, self.image_center[1])
        self.image_center[0] = min(1, self.image_center[0])
        self.image_center[1] = min(1, self.image_center[1])
        #
        self.previous_mouse_position = event.pos()
        self.update()

    def mousePressEvent(self, event):
        self.is_dragging = True
        self.previous_mouse_position = event.pos()
        self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.setCursor(Qt.CrossCursor)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        d_scale = event.angleDelta().y() / 120.0
        if d_scale == 0:
            return
        d_scale = 1.12 ** d_scale
        self.window_zoom *= d_scale
        # Limit zoom-out because you never need more than twice the image dimension to move around
        self.window_zoom = max(0.5, self.window_zoom)
        self.update()

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image is None:
            return
        GL.glBindVertexArray(self.vao)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        self.maybe_upload_image()
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, self.window_zoom)
        GL.glUniform2i(self.window_size_location, self.width(), self.height())
        GL.glUniform2f(self.image_center_location, *self.image_center)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

    def set_image(self, image: PIL.Image.Image):
        self.image = numpy.array(image)
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3] / 255.0
            for rgb in range(3):
                a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
        self.image_needs_upload = True
        # Reset view properties
        self.window_zoom = 1.0
        self.image_center = [0.5, 0.5]
        self.update()

    def maybe_upload_image(self):
        if not self.image_needs_upload:
            return
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
