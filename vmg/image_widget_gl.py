from typing import Optional

import numpy
from OpenGL import GL
import PIL.Image
from PySide6 import QtCore, QtGui, QtOpenGLWidgets, QtWidgets
from PySide6.QtCore import QEvent, Qt, QPoint

from vmg.rect_sel import CursorHolder
from vmg.state import ImageState, ViewState
from vmg.shader import RectangularShader, IImageShader, SphericalShader


class ImageWidgetGL(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)  # noqa
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
        self.rect_shader = RectangularShader()
        self.sphere_shader = SphericalShader()
        self.program: IImageShader = self.rect_shader
        self.view_state = ViewState(window_size=self.size())
        self.view_state.cursor_changed.connect(self.change_cursor)
        self.view_state.request_message.connect(self.request_message)
        self.view_state.sel_rect.selection_shown.connect(self.update)
        self.is_360 = False
        self.raw_rot_ont2 = numpy.eye(2, dtype=numpy.float32)  # For flatty images
        self.raw_rot_ont3 = numpy.eye(3, dtype=numpy.float32)  # For spherical panos

    request_message = QtCore.Signal(str, int)

    @QtCore.Slot(CursorHolder)  # noqa
    def change_cursor(self, cursor_holder: CursorHolder):
        if cursor_holder.cursor is None:
            self.unsetCursor()
        else:
            self.setCursor(cursor_holder.cursor)

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

    def keyPressEvent(self, event):
        self.view_state.key_press_event(event)

    def keyReleaseEvent(self, event):
        self.view_state.key_release_event(event)

    def mouseMoveEvent(self, event):
        if event.pos() is None:
            return
        if self.image is None:
            return
        if event.source() != Qt.MouseEventNotSynthesized:
            return
        if self.view_state.mouse_move_event(event):
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.customContextMenuRequested.emit(event.pos())  # noqa
            return
        else:
            self.view_state.mouse_press_event(event)

    def mouseReleaseEvent(self, event):
        self.view_state.mouse_release_event(event)

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

    @staticmethod
    def _linear_from_srgb(image: numpy.array):
        return numpy.where(image >= 0.04045, ((image + 0.055) / 1.055)**2.4, image/12.92)

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
        if image.mode == "P":
            image = image.convert("RGBA")
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
            self.image = self._linear_from_srgb(self.image)
        else:
            for rgb in range(3):
                self.image[:, :, rgb] = self._linear_from_srgb(self.image[:, :, rgb])  # approximate srgb -> linear
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3]
            for rgb in range(3):
                a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
        self.image_needs_upload = True
        self.signal_360.emit(self.is_360)  # noqa
        w, h = self.image_state.size
        self.image_size_changed.emit(int(w), int(h))  # noqa
        self.update()

    @QtCore.Slot(QPoint)  # noqa
    def show_context_menu(self, qpoint: QPoint):
        menu = QtWidgets.QMenu("Context menu", parent=self)
        menu.addSeparator()
        if self.image is not None:
            for action in self.view_state.context_menu_actions(qpoint):
                menu.addAction(action)
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

    @QtCore.Slot()  # noqa
    def start_rect_with_no_point(self):
        self.view_state.sel_rect.begin(None)
