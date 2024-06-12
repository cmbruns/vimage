from typing import Optional

import numpy
from OpenGL import GL
import PIL.Image
from PySide6 import QtCore, QtGui, QtOpenGLWidgets, QtWidgets
from PySide6.QtCore import QEvent, Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPen

from vmg.state import ImageState, ViewState, LocationQwn
from vmg.shader import RectangularShader, IImageShader, SphericalShader

_exif_orientation_to_matrix = {
    1: numpy.array([[1, 0], [0, 1]], dtype=numpy.float32),
    2: numpy.array([[-1, 0], [0, 1]], dtype=numpy.float32),
    3: numpy.array([[-1, 0], [0, -1]], dtype=numpy.float32),
    4: numpy.array([[1, 0], [0, -1]], dtype=numpy.float32),
    5: numpy.array([[0, 1], [1, 0]], dtype=numpy.float32),
    6: numpy.array([[0, 1], [-1, 0]], dtype=numpy.float32),
    7: numpy.array([[0, -1], [-1, 0]], dtype=numpy.float32),
    8: numpy.array([[0, -1], [1, 0]], dtype=numpy.float32),
}


class ImageWidgetGL(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.OpenHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setMouseTracking(True)
        self.grabGesture(Qt.PinchGesture)
        # self.grabGesture(Qt.PanGesture)
        self.grabGesture(Qt.SwipeGesture)
        self.image: Optional[numpy.ndarray] = None
        self.image_state = None
        self.setMinimumSize(10, 10)
        self.vao = None
        self.texture = None
        self.image_needs_upload = False
        self.is_dragging = False
        self.previous_mouse_position = None
        self.rect_shader = RectangularShader()
        self.sphere_shader = SphericalShader()
        self.program: IImageShader = self.rect_shader
        self.view_state = ViewState(window_size=self.size())
        self.is_360 = False
        self.raw_rot_ont2 = numpy.eye(2, dtype=numpy.float32)  # For flatty images
        self.raw_rot_ont3 = numpy.eye(3, dtype=numpy.float32)  # For spherical panos

    request_message = QtCore.Signal(str, int)

    def event(self, event: QEvent):
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            swipe = event.gesture(Qt.SwipeGesture)
            if swipe is not None:
                print(swipe)
            elif pinch is not None:
                zoom = pinch.scaleFactor()
                self.view_state.zoom_relative(zoom, None)
                self.update()
                return True

        return super().event(event)

    def _hover_pixel(self, qpoint: QPoint) -> bool:
        p_qwn = LocationQwn.from_qpoint(qpoint)
        if self.is_360:
            p_hpd = self.view_state.hpd_for_qwn(p_qwn)
            self.request_message.emit(  # noqa
                f"heading = {p_hpd.heading:.1f}°  pitch = {p_hpd.pitch:.1f}°",
                2000,
            )
        else:
            p_omp = self.view_state.omp_for_qwn(p_qwn)
            self.request_message.emit(  # noqa
                f"image pixel = [{int(p_omp.x)}, {int(p_omp.y)}]",
                2000,
            )
        return False  # Nothing changed, so no update needed

    def initializeGL(self) -> None:
        # Use native-like background color
        bg_color = self.palette().color(self.backgroundRole()).getRgbF()
        GL.glClearColor(*bg_color)
        # Make transparent images transparent
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # Using premultiplied alpha
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.rect_shader.initialize_gl()
        self.sphere_shader.initialize_gl()
        self.texture = GL.glGenTextures(1)

    def mouseMoveEvent(self, event):
        if event.pos() is None:
            return
        if self.image is None:
            return
        if event.source() != Qt.MouseEventNotSynthesized:
            return
        if self.is_dragging:
            self.view_state.drag_relative(event.pos(), self.previous_mouse_position)
            self.previous_mouse_position = event.pos()
            self.update()
        else:
            self._hover_pixel(event.pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.customContextMenuRequested.emit(event.pos())
            return
        self.is_dragging = True
        self.previous_mouse_position = event.pos()
        self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.previous_mouse_position = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        d_scale = event.angleDelta().y() / 120.0
        if d_scale == 0:
            return
        d_scale = 1.12 ** d_scale
        self.view_state.zoom_relative(d_scale, event.position())
        self.update()

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image is None:
            return
        GL.glBindVertexArray(self.vao)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        self.maybe_upload_image()
        self.program.paint_gl(self.view_state)

    def resizeGL(self, w, h):
        # TODO: do we ever need to check the size outside of ViewState?
        self.view_state.set_window_size(w, h)

    def set_image(self, image: PIL.Image.Image):
        self.image_state = ImageState(image)
        self.view_state.reset()
        self.view_state.set_360(self.image_state.is_360)
        self.view_state.set_image_state(self.image_state)
        if self.view_state.is_360:
            self.is_360 = True
            self.program = self.sphere_shader
        else:
            self.is_360 = False
            self.program = self.rect_shader
        self.image = numpy.array(image)
        # Normalize values to maximum 1.0 and convert to float32
        # TODO: test performance
        max_values = {
            numpy.dtype("bool"): 1,
            numpy.dtype("uint8"): 255,
            numpy.dtype("uint16"): 65535,
            numpy.dtype("float32"): 1.0,
        }
        self.image = self.image.astype(numpy.float32) / max_values[self.image.dtype]
        # Convert srgb value scale to linear
        if len(self.image.shape) == 2:
            # Monochrome image
            self.image = numpy.square(self.image)  # approximate srgb -> linear
        else:
            for rgb in range(3):
                # square() method below crashes on Mac with numpy 1.25. OK with 1.26
                self.image[:, :, rgb] = numpy.square(self.image[:, :, rgb])  # approximate srgb -> linear
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3]
            for rgb in range(3):
                a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
        self.image_needs_upload = True
        self.signal_360.emit(self.is_360)  # noqa
        w, h = self.image_state.size
        self.image_size_changed.emit(int(w), int(h))
        self.update()

    @QtCore.Slot(QPoint)
    def show_context_menu(self, qpoint: QPoint):
        print("context menu")
        menu = QtWidgets.QMenu("Context menu", parent=self)
        menu.addSeparator()
        menu.addAction(QtGui.QAction("Start selecting a rectangle here", self))
        menu.addSeparator()
        menu.addAction(QtGui.QAction("Cancel [ESC]", self))
        menu.exec(self.mapToGlobal(qpoint))

    image_size_changed = QtCore.Signal(int, int)
    signal_360 = QtCore.Signal(bool)

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
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        self.image_needs_upload = False
