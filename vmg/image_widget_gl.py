from enum import Enum

import pkg_resources

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileShader
import PIL
from PySide6 import QtGui, QtOpenGLWidgets
from PySide6.QtCore import QEvent, Qt


class ImageWidgetGL(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.PinchGesture)
        # self.grabGesture(Qt.PanGesture)
        self.grabGesture(Qt.SwipeGesture)
        self.image: numpy.ndarray = None
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
        self.pixelFilter = PixelFilter.CATMULL_ROM
        self.pixelFilter_location = None

    def clamp_center(self):
        # Keep the center point on the actual image itself
        self.image_center[0] = max(0.0, self.image_center[0])
        self.image_center[1] = max(0.0, self.image_center[1])
        self.image_center[0] = min(1.0, self.image_center[0])
        self.image_center[1] = min(1.0, self.image_center[1])
        z = self.window_zoom
        if z <= 1:
            self.image_center[0] = 0.5
            self.image_center[1] = 0.5
        else:
            self.image_center[0] = min(self.image_center[0], 1 - 0.5 / z)
            self.image_center[0] = max(self.image_center[0], 0.5 / z)
            self.image_center[1] = min(self.image_center[1], 1 - 0.5 / z)
            self.image_center[1] = max(self.image_center[1], 0.5 / z)

    def event(self, event: QEvent):
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            swipe = event.gesture(Qt.SwipeGesture)
            if swipe is not None:
                print(swipe)
            elif pinch is not None:
                zoom = pinch.scaleFactor()
                self.zoom_relative(zoom)
                self.update()
                return True

        return super().event(event)

    def image_for_window(self, wpos):
        x_scale = y_scale = self.window_zoom
        ratio_ratio = self.width() * self.image.shape[0] / (self.height() * self.image.shape[1])
        if ratio_ratio > 1:
            x_scale /= ratio_ratio
        else:
            y_scale *= ratio_ratio
        wx = (wpos.x() - self.width() / 2) / self.width() / x_scale
        wy = (wpos.y() - self.height() / 2) / self.height() / y_scale
        return wx, wy

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
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        # self.shader = compileProgram(vertex_shader, fragment_shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.image_center_location = GL.glGetUniformLocation(self.shader, "image_center")
        #
        self.texture = GL.glGenTextures(1)
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")

    def mouseMoveEvent(self, event):
        if not self.is_dragging:
            return
        if self.image is None:
            return
        if event.source() != Qt.MouseEventNotSynthesized:
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
        self.image_center[0] += dx / x_scale
        self.image_center[1] += dy / y_scale
        self.clamp_center()
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
        self.zoom_relative(d_scale, event.position())
        self.update()

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image is None:
            return
        GL.glBindVertexArray(self.vao)
        #
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        self.maybe_upload_image()
        # both nearest and catrom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, self.window_zoom)
        GL.glUniform2i(self.window_size_location, self.width(), self.height())
        GL.glUniform2f(self.image_center_location, *self.image_center)
        GL.glUniform1i(self.pixelFilter_location, self.pixelFilter.value)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

    def set_image(self, image: PIL.Image.Image):
        self.image = numpy.array(image)
        # Normalize values to maximum 1.0 and convert to float32
        max_vals = {
            numpy.dtype("uint8"): 255,
            numpy.dtype("uint16"): 65535,
            numpy.dtype("float32"): 1.0,
        }
        self.image = self.image.astype(numpy.float32) / max_vals[self.image.dtype]
        # Convert srgb value scale to linear
        for rgb in range(3):
            self.image[:, :, rgb] = numpy.square(self.image[:, :, rgb])  # approximate srgb -> linear
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3]
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
            numpy.dtype("float32"): GL.GL_FLOAT,
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

    def zoom_relative(self, zoom_factor: float, zoom_center=None):
        new_zoom = self.window_zoom * zoom_factor
        if new_zoom <= 1:
            zoom_factor = 1 / self.window_zoom
            new_zoom = 1
        self.window_zoom = new_zoom
        if zoom_center is not None:
            z2 = self.image_for_window(zoom_center)  # After position
            z1 = [x * zoom_factor for x in z2]  # Before position
            dx = z2[0] - z1[0]
            dy = z2[1] - z1[1]
            self.image_center[0] -= dx
            self.image_center[1] -= dy
        # Limit zoom-out because you never need more than twice the image dimension to move around
        self.window_zoom = max(1.0, self.window_zoom)
        self.clamp_center()


class PixelFilter(Enum):
    SHARP = 1
    BILINEAR = 2
    HERMITE = 3
    CATMULL_ROM = 4
