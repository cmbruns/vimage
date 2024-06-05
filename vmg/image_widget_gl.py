from math import cos, radians, sin

from typing import Optional

import numpy
from OpenGL import GL
import PIL
from PIL import ExifTags
from PySide6 import QtCore, QtGui, QtOpenGLWidgets
from PySide6.QtCore import QEvent, Qt

from vmg.coordinate import WindowPos, NdcPos
from vmg.pixel_filter import PixelFilter
from vmg.view_model import RectangularViewState, RectangularShader, IViewState, IImageShader, SphericalViewState, \
    SphericalShader

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
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setMouseTracking(True)
        self.grabGesture(Qt.PinchGesture)
        # self.grabGesture(Qt.PanGesture)
        self.grabGesture(Qt.SwipeGesture)
        self.image: Optional[numpy.ndarray] = None
        self.setMinimumSize(10, 10)
        self.vao = None
        self.texture = None
        self.image_needs_upload = False
        self.is_dragging = False
        self.previous_mouse_position = None
        self.pixel_filter = PixelFilter.CATMULL_ROM
        self.rect_shader = RectangularShader()
        self.sphere_shader = SphericalShader()
        self.program: IImageShader = self.rect_shader
        self.rect_view_state: IViewState = RectangularViewState()
        self.sphere_view_state: IViewState = SphericalViewState()
        self.view_state = self.rect_view_state
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
                self.view_state.zoom_relative(zoom, None, self)
                self.sphere_view_state.zoom_relative(zoom, None, self)
                self.update()
                return True

        return super().event(event)

    def _hover_pixel(self, win_xy: WindowPos) -> bool:
        # TODO: draw square around pixel
        p_ndc = NdcPos.from_window(win_xy, self.width(), self.height())

        # coordinate systems:
        #  ndc - normalized device coordinates ; range -1,1 ; origin at center ; positive y up
        #  win - window ; origin at center ; units window pixels ; positive y up ; origin at center
        #  ont - oriented image coordinates ; units image pixels ; positive y down ; origin at center
        #  raw - raw image coordinates (before EXIF orientation correction) ; origin at center
        #  ulc - raw image with origin at upper left
        #  tex - texture coordinates ; range (0, 1)

        # TODO: use these transformations in shader
        # centered window pixel coordinates [changes with window size]
        cwn_from_ndc = numpy.array([
            [self.width()/2, 0],
            [0, self.height()/2],
        ], dtype=numpy.float32)
        p_cwn = cwn_from_ndc @ p_ndc

        # centered, rotation corrected image dimensions [changes with window size and image size]
        raw_height, raw_width = self.image.shape[0:2]  # Unrotated dimension
        ont_width, ont_height = [abs(x) for x in (self.raw_rot_ont2 @ [raw_width, raw_height])]
        # zoom value depends on relative aspect ratio of window to image
        if self.width() / self.height() > ont_width / ont_height:
            # window aspect is wider than image aspect, so zoom by height
            rc_scale = ont_height / self.height() / self.view_state.window_zoom
        else:
            rc_scale = ont_width / self.width() / self.view_state.window_zoom
        ont_from_cwn = numpy.array([
            [rc_scale, 0],
            [0, -rc_scale],  # Flip Y when converting window coordinates to image coordinates
        ], dtype=numpy.float32)
        p_ont = ont_from_cwn @ p_cwn

        # raw unrotated centered image coordinates [changes with image metadata]
        ucimg_from_ont = self.raw_rot_ont2
        p_ucimg = ucimg_from_ont @ p_ont

        # move origin from center to upper left corner [changes with image size]
        ulimg_from_ucimg = numpy.array([
            [1, 0, raw_width/2],
            [0, 1, raw_height/2],
            [0, 0, 1],
        ], dtype=numpy.float32)
        p_ulimg = (ulimg_from_ucimg @ [*p_ucimg, 1])[0:2]

        # convert to texture coordinates
        texc_from_ulimg = numpy.array([
            [1 / raw_width, 0],
            [0, 1 / raw_height],
        ], dtype=numpy.float32)
        p_texc = texc_from_ulimg @ p_ulimg

        img_x, img_y = self.view_state.image_for_window(win_xy, self)
        pxl_x = (img_x + 0.5) * ont_width
        pxl_y = (img_y + 0.5) * ont_height
        self.request_message.emit(  # noqa
            # f"p_texc = {p_texc}"
            # f"{win_xy}; "
            # f"rc_scale = {rc_scale}; "
            # f"{ndc}; "
            # f"cwn = {p_cwn}; "
            # f"p_ont = {p_ont}"
            # f"p_ulimg = {p_ulimg}"
            # f"cimg dims = [{ont_width},{ont_height}]; "
            # f"image = [{img_x:.4f}, {img_y:.4f}]; "
            f"image pixel = [{pxl_x:.1f}, {pxl_y:.1f}]"
            , 2000)
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
        if not self.is_dragging:
            update_needed = self._hover_pixel(WindowPos.from_qpoint(event.pos()))
            if update_needed:
                self.update()
            return
        # Drag image around
        dx = event.pos().x() - self.previous_mouse_position.x()
        dy = event.pos().y() - self.previous_mouse_position.y()
        self.view_state.drag_relative(dx, dy, self)
        self.sphere_view_state.drag_relative(dx, dy, self)  # TODO: redundant?
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
        win_xy = (event.position().x(), event.position().y())
        self.sphere_view_state.zoom_relative(d_scale, win_xy, self)
        self.view_state.zoom_relative(d_scale, win_xy, self)
        self.update()

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.image is None:
            return
        GL.glBindVertexArray(self.vao)
        #
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        self.maybe_upload_image()
        self.view_state.pixel_filter = self.pixel_filter
        self.program.paint_gl(self.view_state, self)

    def set_image(self, image: PIL.Image.Image):
        exif0 = image.getexif()
        exif = {
            PIL.ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in PIL.ExifTags.TAGS
        }
        for ifd_id in ExifTags.IFD:
            try:
                ifd = exif0.get_ifd(ifd_id)
                if ifd_id == ExifTags.IFD.GPSInfo:
                    resolve = ExifTags.GPSTAGS
                else:
                    resolve = ExifTags.TAGS
                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    exif[tag] = v
            except KeyError:
                pass
        xmp = image.getxmp()
        # Check for orientation metadata
        orientation_code: int = exif.get("Orientation", 1)
        self.raw_rot_ont2 = _exif_orientation_to_matrix.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        # Check for 360 panorama image
        if image.width == 2 * image.height:
            try:
                self.is_360 = True
                self.view_state = self.sphere_view_state
                self.program = self.sphere_shader
                try:
                    # TODO: InitialViewHeadingDegrees
                    desc = xmp["xmpmeta"]["RDF"]["Description"]
                    heading = radians(float(desc["PoseHeadingDegrees"]))
                    pitch = radians(float(desc["PosePitchDegrees"]))
                    roll = radians(float(desc["PoseRollDegrees"]))
                    self.raw_rot_ont3 = numpy.array([
                        [cos(roll), -sin(roll), 0],
                        [sin(roll), cos(roll), 0],
                        [0, 0, 1],
                    ], dtype=numpy.float32)
                    self.raw_rot_ont3 = self.raw_rot_ont3 @ [
                        [1, 0, 0],
                        [0, cos(pitch), sin(pitch)],
                        [0, -sin(pitch), cos(pitch)],
                    ]
                    print(heading, pitch, roll)
                except KeyError:
                    pass
                if exif["Model"].lower().startswith("ricoh theta"):
                    # print("360")
                    pass  # TODO 360 image
            except KeyError:
                pass
        else:
            self.is_360 = False
            self.view_state = self.rect_view_state
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
                self.image[:, :, rgb] = numpy.square(self.image[:, :, rgb])  # approximate srgb -> linear
        # Use premultiplied alpha for better filtering
        if image.mode == "RGBA":
            a = self.image
            alpha_layer = a[:, :, 3]
            for rgb in range(3):
                a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
        self.image_needs_upload = True
        self.sphere_view_state.reset()
        self.rect_view_state.reset()
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
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        self.image_needs_upload = False
