from math import radians

import logging

import numpy
from OpenGL import GL
from PySide6 import QtCore, QtGui, QtOpenGLWidgets, QtWidgets
from PySide6.QtCore import QEvent, Qt, QPoint

from vmg.image_data import ImageData, InputFormat
from vmg.offscreen_context import OffscreenContext
from vmg.selection_box import (CursorHolder)
from vmg.state import ViewState
from vmg.shader import IImageShader, SphericalShader, RectangularTileShader

logger = logging.getLogger(__name__)


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
        self.sphere_shader = SphericalShader()
        self.rect_tile_shader = RectangularTileShader()
        self.program: IImageShader = self.rect_tile_shader
        self.view_state = ViewState(window_size=self.size())
        self.view_state.cursor_changed.connect(self.change_cursor)
        self.view_state.request_message.connect(self.request_message)
        self.view_state.sel_rect.selection_shown.connect(self.update)
        self.raw_rot_ont2 = numpy.eye(2, dtype=numpy.float32)  # For flatty images
        self.raw_rot_ont3 = numpy.eye(3, dtype=numpy.float32)  # For spherical panos
        self.offscreen_context_is_ready = False

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

    image_displayed = QtCore.Signal(ImageData)

    image_size_changed = QtCore.Signal(int, int)

    def initializeGL(self) -> None:
        logger.debug("Starting initializeGL()...")
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
        self.rect_tile_shader.initialize_gl()
        self.sphere_shader.initialize_gl()

    input_format_changed = QtCore.Signal(InputFormat)

    def keyPressEvent(self, event):
        self.view_state.key_press_event(event)

    def keyReleaseEvent(self, event):
        self.view_state.key_release_event(event)

    load_failed = QtCore.Signal(str)

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

    def create_offscreen_context(self):
        display_ctx = self.context()
        offscreen_context = OffscreenContext(self, display_ctx, self.format())
        offscreen_context.init_gl()
        main_window = self.window()
        if main_window is not None and hasattr(main_window, "loading_thread"):
            offscreen_context.context.moveToThread(main_window.loading_thread)
        logger.debug("Created shared offscreen OpenGL context")
        self.context_created.emit(offscreen_context)  # noqa

    def paintGL(self) -> None:
        logger.debug("Starting paintGL()")
        self.view_state.background_color = self.palette().color(self.backgroundRole()).getRgbF()
        GL.glClearColor(*self.view_state.background_color)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image_data is None:
            logger.debug("image_data is None")
            return
        GL.glBindVertexArray(self.vao)
        if not self.image_data.has_displayed:
            self.progress_changed.emit(95)  # noqa
        self.program.paint_gl(self.view_state, self.image_data.texture)
        if not self.image_data.has_displayed:
            self.image_data.has_displayed = True
            self.progress_changed.emit(98)  # noqa
            self.image_displayed.emit(self.image_data)  # noqa
        logger.debug("Finished paintGL()")

    progress_changed = QtCore.Signal(int)

    request_message = QtCore.Signal(str, int)

    def resizeGL(self, w, h):
        # TODO: do we ever need to check the size outside of ViewState?
        self.view_state.set_window_size(w, h)

    @staticmethod
    def _linear_from_srgb(image: numpy.array):
        return numpy.where(image >= 0.04045, ((image + 0.055) / 1.055)**2.4, image/12.92)

    def set_input_format(self, input_format: InputFormat) -> bool:
        if self.view_state.input_format == input_format:
            return False
        self.view_state.set_input_format(input_format)
        if input_format == InputFormat.EQUIRECTANGULAR:
            self.program = self.sphere_shader
        elif input_format == InputFormat.DUAL_FISHEYE:
            self.program = self.sphere_shader
        elif input_format == InputFormat.STANDARD_PHOTO:
            self.program = self.rect_tile_shader
        else:
            raise Exception("Unexpected input format")
        self.signal_360.emit(input_format != InputFormat.STANDARD_PHOTO)  # noqa
        logger.info(f"input projection = {input_format}")
        self.input_format_changed.emit(input_format)
        return True

    def set_image_data(self, image_data: ImageData):
        logger.info("Received image data")
        self.image_data = image_data
        self.view_state.reset()
        self.view_state.set_image_data(self.image_data)
        self.set_input_format(self.image_data.input_format)
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

    @QtCore.Slot(float)
    def update_df_fov(self, fov_deg: float):
        fov_rad = radians(fov_deg)
        if fov_rad == self.sphere_shader.df_fov_radians:
            return  # No change
        self.sphere_shader.df_fov_radians = fov_rad
        if self.program != self.sphere_shader:
            return  # Wrong shader, no update needed
        if self.view_state.input_format != InputFormat.DUAL_FISHEYE:
            return  # Wrong format, no update needed
        self.update()  # Live update as user changes parameter

    @QtCore.Slot(float)
    def update_df_lens_rot(self, rot_deg: float):
        rot_rad = radians(rot_deg)
        if rot_rad == self.sphere_shader.df_lens_rot_radians:
            return  # No change
        self.sphere_shader.df_lens_rot_radians = rot_rad
        if self.program != self.sphere_shader:
            return  # Wrong shader, no update needed
        if self.view_state.input_format != InputFormat.DUAL_FISHEYE:
            return  # Wrong format, no update needed
        self.update()  # Live update as user changes parameter

    def wheelEvent(self, event: QtGui.QWheelEvent):
        d_scale = event.angleDelta().y() / 120.0
        if d_scale == 0:
            return
        d_scale = 1.12 ** d_scale
        self.view_state.zoom_relative(d_scale, event.position())
        self.update()
