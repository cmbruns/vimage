import numpy
from OpenGL import GL
from PySide6 import QtCore, QtGui, QtOpenGLWidgets, QtWidgets
from PySide6.QtCore import QEvent, Qt, QPoint

from vmg.image_data import ImageData
from vmg.offscreen_context import OffscreenContext
from vmg.selection_box import (CursorHolder)
from vmg.state import ViewState
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
        self.image_data = None
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

    @QtCore.Slot(CursorHolder)  # noqa
    def change_cursor(self, cursor_holder: CursorHolder):
        if cursor_holder.cursor is None:
            self.unsetCursor()
        else:
            self.setCursor(cursor_holder.cursor)

    context_created = QtCore.Signal(OffscreenContext)

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

    image_size_changed = QtCore.Signal(int, int)

    def initializeGL(self) -> None:
        # Use native-like background color
        bg_color = self.palette().color(self.backgroundRole()).getRgbF()
        GL.glClearColor(*bg_color)
        # Make transparent images transparent
        # Framebuffer is premultiplied alpha
        # but textures are straight alpha
        GL.glEnable(GL.GL_BLEND)
        # traditional glBlendFunc has poor hardware filtering of transparent pixels
        # GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)  # poor filtering
        # GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # with premultiplied alpha
        # Use glBlendFuncSeparate to simulate premultiplied alpha, without needing to munge pixels
        GL.glBlendFuncSeparate(
            GL.GL_SRC_ALPHA,  # simulate premultiplied alpha on srcRGB
            GL.GL_ONE_MINUS_SRC_ALPHA,  # blend dstRGB
            GL.GL_ONE,  # combine srcAlpha as-is
            GL.GL_ONE_MINUS_SRC_ALPHA  # blend dstAlpha
        )
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.rect_shader.initialize_gl()
        self.sphere_shader.initialize_gl()
        self.texture = GL.glGenTextures(1)
        offscreen_context = OffscreenContext(self, self.context(), self.format())
        self.context_created.emit(offscreen_context)

    def keyPressEvent(self, event):
        self.view_state.key_press_event(event)

    def keyReleaseEvent(self, event):
        self.view_state.key_release_event(event)

    def mouseMoveEvent(self, event):
        if event.pos() is None:
            return
        if self.image_data is None:
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

    def paintGL(self) -> None:
        bg_color = self.palette().color(self.backgroundRole()).getRgbF()
        self.rect_shader.background_color[:] = bg_color[:]
        GL.glClearColor(*bg_color)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image_data is None:
            return
        GL.glBindVertexArray(self.vao)
        self.image_data.texture.bind_gl()
        self.program.paint_gl(self.view_state)

    request_message = QtCore.Signal(str, int)

    def resizeGL(self, w, h):
        # TODO: do we ever need to check the size outside of ViewState?
        self.view_state.set_window_size(w, h)

    @staticmethod
    def _linear_from_srgb(image: numpy.array):
        return numpy.where(image >= 0.04045, ((image + 0.055) / 1.055)**2.4, image/12.92)

    def set_image_data(self, image_data: ImageData):
        self.image_data = image_data
        self.view_state.reset()
        self.view_state.set_360(self.image_data.is_360)
        self.view_state.set_image_data(self.image_data)
        if self.view_state.is_360:
            self.is_360 = True
            self.program = self.sphere_shader
        else:
            self.is_360 = False
            self.program = self.rect_shader
        self.image_needs_upload = True
        self.signal_360.emit(self.is_360)  # noqa
        w, h = self.image_data.size
        self.image_size_changed.emit(int(w), int(h))  # noqa
        self.update()

    @QtCore.Slot(QPoint)  # noqa
    def show_context_menu(self, qpoint: QPoint):
        menu = QtWidgets.QMenu("Context menu", parent=self)
        menu.addSeparator()
        if self.image_data is not None:
            for action in self.view_state.context_menu_actions(qpoint):
                menu.addAction(action)
        menu.addSeparator()
        menu.addAction(QtGui.QAction("Cancel [ESC]", self))
        menu.exec(self.mapToGlobal(qpoint))

    signal_360 = QtCore.Signal(bool)

    @QtCore.Slot()  # noqa
    def start_rect_with_no_point(self):
        self.view_state.sel_rect.begin(None)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        d_scale = event.angleDelta().y() / 120.0
        if d_scale == 0:
            return
        d_scale = 1.12 ** d_scale
        self.view_state.zoom_relative(d_scale, event.position())
        self.update()
