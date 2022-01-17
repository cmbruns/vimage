import numpy
from OpenGL import GL
import PIL
from PySide6 import QtGui, QtOpenGLWidgets
from PySide6.QtCore import QEvent, Qt

from vmg.pixel_filter import PixelFilter
from vmg.view_model import RectangularViewModel


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
        self.texture = None
        self.image_needs_upload = False
        self.is_dragging = False
        self.previous_mouse_position = None
        self.pixel_filter = PixelFilter.CATMULL_ROM
        self.view_model = RectangularViewModel()

    def event(self, event: QEvent):
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            swipe = event.gesture(Qt.SwipeGesture)
            if swipe is not None:
                print(swipe)
            elif pinch is not None:
                zoom = pinch.scaleFactor()
                self.view_model.zoom_relative(zoom, None, self)
                self.update()
                return True

        return super().event(event)

    def image_for_window(self, wpos):
        x_scale = y_scale = self.view_model.window_zoom
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
        self.view_model.initializeGL()
        self.texture = GL.glGenTextures(1)

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
        self.view_model.drag_relative(dx, dy, self)
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
        self.view_model.zoom_relative(d_scale, event.position(), self)
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
        #
        self.view_model.pixel_filter = self.pixel_filter
        self.view_model.paintGL(self)

    def set_image(self, image: PIL.Image.Image):
        # TODO: support 360 image view
        exif = exif = {
            PIL.ExifTags.TAGS[k]: v
            for k, v in image.getexif().items()
            if k in PIL.ExifTags.TAGS
        }
        if image.width == 2 * image.height:
            try:
                if exif["Model"].lower().startswith("ricoh theta"):
                    print("360")
                    pass  # TODO 360 image
            except KeyError:
                pass
        print(exif)
        self.image = numpy.array(image)
        print(image.info)
        # Normalize values to maximum 1.0 and convert to float32
        # TODO: test performance
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
        self.view_model.reset()
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
