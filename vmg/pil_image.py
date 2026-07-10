"""
Intended as partial Replacement for ImageData, Texture
"""

from ctypes import c_float, c_void_p, cast, sizeof
import enum
import logging
from math import cos, radians, sin
from typing import Iterator

import numpy
from OpenGL import GL
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT
from PySide6 import QtCore
from numpy.typing import NDArray
import PIL
from PIL import ExifTags, Image

from vmg.exif_orientation import ExifOrientation
from vmg.frame import DimensionsOmp
from vmg.input_format import InputFormat
from vmg.interfaces import ImageLike, TileLike
from vmg.photometric_scale import PhotometricScale

logger = logging.getLogger(__name__)
GLenum = int
GLint = int


class LoadProgress(enum.Enum):
    NONE = 1
    METADATA_LOADED = 2
    ARRAYS_CREATED = 3
    TILES_CREATED = 4
    TILES_UPLOADED = 5
    DISPLAYED = 6


gl_type_for_numpy_dtype = {
    numpy.dtype("int8"): GL.GL_BYTE,
    numpy.dtype("uint8"): GL.GL_UNSIGNED_BYTE,
    numpy.dtype("int16"): GL.GL_SHORT,
    numpy.dtype("uint16"): GL.GL_UNSIGNED_SHORT,
    numpy.dtype("int32"): GL.GL_INT,
    numpy.dtype("uint32"): GL.GL_UNSIGNED_INT,
    numpy.dtype("float16"): GL.GL_HALF_FLOAT,
    numpy.dtype("float32"): GL.GL_FLOAT,
    numpy.dtype("float64"): GL.GL_DOUBLE,
}

internal_format_for_channel_count = {
    1: GL.GL_RED,
    2: GL.GL_RG,
    3: GL.GL_RGB,
    4: GL.GL_RGBA,
}


rotation_for_exif_orientation = {
    1: numpy.array([[1, 0], [0, 1]], dtype=numpy.float32),
    2: numpy.array([[-1, 0], [0, 1]], dtype=numpy.float32),
    3: numpy.array([[-1, 0], [0, -1]], dtype=numpy.float32),
    4: numpy.array([[1, 0], [0, -1]], dtype=numpy.float32),
    5: numpy.array([[0, 1], [1, 0]], dtype=numpy.float32),
    6: numpy.array([[0, 1], [-1, 0]], dtype=numpy.float32),
    7: numpy.array([[0, -1], [-1, 0]], dtype=numpy.float32),
    8: numpy.array([[0, -1], [1, 0]], dtype=numpy.float32),
}


class ImageSignallerQt(QtCore.QObject):
    progress_changed = QtCore.Signal(int)
    image_displayed = QtCore.Signal(ImageLike)


class BasicImageLike(ImageLike):
    def __init__(self):
        self.sq = ImageSignallerQt()
        self._tiles = []
        self._file_name = None
        # Reasonable defaults
        self._input_format = InputFormat.STANDARD_PHOTO
        self._photometric_scale = PhotometricScale.SRGB
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self._size_raw = (0, 0)
        self._size_omp = DimensionsOmp(0, 0)
        self.load_progress = LoadProgress.NONE
        self._orientation = ExifOrientation.ROTATE_0

    @property
    def file_name(self) -> str:
        return self._file_name

    @property
    def input_format(self) -> InputFormat:
        return self._input_format

    @property
    def orientation(self) -> ExifOrientation:
        return self._orientation

    @property
    def photometric_scale(self) -> PhotometricScale:
        return self._photometric_scale

    @property
    def raw_rot_ont(self) -> NDArray[numpy.floating]:
        return self._raw_rot_ont

    @property
    def size_omp(self) -> DimensionsOmp:
        return self._size_omp

    @property
    def size_raw(self) -> tuple[int, int]:
        return self._size_raw

    def initialize_gl(self) -> None:
        raise NotImplementedError

    def paint_gl(self) -> None:
        is_complete = True  # start optimistic
        for tile in self.tiles():
            if not tile.paint_gl():
                is_complete = False
            if is_complete and self.load_progress != LoadProgress.DISPLAYED:
                self.load_progress = LoadProgress.DISPLAYED
                self.sq.image_displayed.emit(self)  # noqa

    def tiles(self) -> Iterator[TileLike]:  # noqa
        yield from self._tiles


class InappropriateImageLoader(OSError):
    pass


class PilImage(BasicImageLike):
    def __init__(self, file_name: str):
        super().__init__()
        try:
            pil_image = Image.open(file_name)
        except PIL.UnidentifiedImageError as e:
            raise InappropriateImageLoader() from e
        self._file_name = file_name
        self.pil_image = pil_image  # TODO: MainWindow needs refactor
        self.sq.progress_changed.emit(2)  # noqa
        self.load_pil_metadata(pil_image)
        # Create numpy array of image
        self.sq.progress_changed.emit(15)  # noqa
        self.array = self.construct_pil_array(pil_image)

    @staticmethod
    def construct_pil_array(img: Image.Image) -> NDArray:
        if img.mode in ["P",]:  # Palette image
            img = img.convert("RGBA")  # TODO: palette shader
        return numpy.asarray(img)

    def initialize_gl(self) -> None:
        """
        Construct tiles to be rendered
        Call from loading thread with OpenGL context current
        """
        tile_size = 8192
        max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)  # noqa
        assert max_texture_size >= tile_size
        # Loop over tiles
        top = 0
        # pad tiles by 2 pixels so cubic interpolation is seamless
        top_pad = 0
        bottom_pad = 2
        w, h = self.size_raw  # TODO: raw or logical?
        channel_count = 1
        if len(self.array.shape) > 2:
            channel_count = self.array.shape[2]
        internal_format = internal_format_for_channel_count[channel_count]
        tex_format = internal_format  # TODO: BGR, GL_RGB16 etc.
        data_type = gl_type_for_numpy_dtype[self.array.dtype]
        while top <= h:
            if top + tile_size - 4 >= h:  # TODO: is 4 correct here?
                bottom_pad = 0
            left = 0
            left_pad = 0
            right_pad = 2
            while left <= w:
                if left + tile_size - 4 >= w:
                    right_pad = 0
                width = min(tile_size, w - left)
                height = min(tile_size, h - top)
                tile = Tile(
                    image=self,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    left_pad=left_pad,
                    top_pad=top_pad,
                    right_pad=right_pad,
                    bottom_pad=bottom_pad,
                    internal_format=internal_format,
                    tex_format=tex_format,
                    data_type=data_type,
                )
                self._tiles.append(tile)
                tile.initialize_gl()
                left += tile_size - 4
                left_pad = 2
            top += tile_size - 4
            top_pad = 2

    def load_pil_metadata(self, pil_image):
        # Size
        self._size_raw = pil_image.size
        self._size_omp = pil_image.size  # for now
        # Extract exif and xmp metadata
        exif0 = pil_image.getexif()
        exif = {
            PIL.ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in PIL.ExifTags.TAGS
        }
        for ifd_id in PIL.ExifTags.IFD:
            try:
                ifd = exif0.get_ifd(ifd_id)
                if ifd_id == PIL.ExifTags.IFD.GPSInfo:
                    resolve = PIL.ExifTags.GPSTAGS
                else:
                    resolve = PIL.ExifTags.TAGS
                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    exif[tag] = v
            except KeyError:
                pass
        try:
            xmp = pil_image.getxmp()  # noqa
        except AttributeError:
            xmp = {}
        # EXIF orientation
        orientation_code: int = exif.get("Orientation", 1)
        self._orientation = ExifOrientation(orientation_code)
        raw_rot_omp = rotation_for_exif_orientation.get(
            orientation_code, numpy.eye(2, dtype=numpy.float32))
        self._size_omp = DimensionsOmp(*[abs(x) for x in (
                raw_rot_omp.T @ self.size_raw)])
        # Input format
        model = exif.get("Model", "").lower()
        w, h = self.size_omp.x, self.size_omp.y
        if w != h * 2:
            self._input_format = InputFormat.STANDARD_PHOTO
        elif model == "sm-c200" and ((w, h) == (7776, 3888) or (w, h) == (5792, 2896)):
            # 2016 Gear 360 raw image
            self._input_format = InputFormat.DUAL_FISHEYE
        elif model.startswith("ricoh theta"):
            self._input_format = InputFormat.EQUIRECTANGULAR
        else:
            self._input_format = InputFormat.STANDARD_PHOTO
        # raw_rot_ont  panorama camera orientation
        try:
            # TODO: InitialViewHeadingDegrees
            desc = xmp["xmpmeta"]["RDF"]["Description"]
            heading = radians(float(desc["PoseHeadingDegrees"]))
            pitch = radians(float(desc["PosePitchDegrees"]))
            roll = radians(float(desc["PoseRollDegrees"]))
            m = numpy.array([
                [cos(roll), -sin(roll), 0],
                [sin(roll), cos(roll), 0],
                [0, 0, 1],
            ], dtype=numpy.float32)
            m = m @ [
                [1, 0, 0],
                [0, cos(pitch), sin(pitch)],
                [0, -sin(pitch), cos(pitch)],
            ]
            m = m @ [
                [cos(heading), 0, sin(heading)],
                [0, 1, 0],
                [-sin(heading), 0, cos(heading)],
            ]
            self._raw_rot_ont = m
        except (KeyError, TypeError):
            pass


class Tile(TileLike):
    def __init__(
            self,
            image: ImageLike,
            # portion of the image covered by this tile
            left: int,
            top: int,
            width: int,
            height: int,
            left_pad: int,
            top_pad: int,
            right_pad: int,
            bottom_pad: int,
            internal_format: GLenum,
            tex_format: GLenum,
            data_type: GLenum,
    ):
        self.image = image
        self.internal_format = internal_format
        self.tex_format = tex_format
        self.data_type = data_type
        self.vao = None
        self.vbo = None
        # Convert to oriented image pixel coordinates (omp)
        left_rmp = left + left_pad
        right_rmp = left + width - right_pad
        top_rmp = top + top_pad
        bottom_rmp = top + height - bottom_pad
        left_omp, top_omp = omp_for_rmp((left_rmp, top_rmp), image.size_raw, image.orientation)
        right_omp, bottom_omp = omp_for_rmp((right_rmp, bottom_rmp), image.size_raw, image.orientation)
        left_tc = left_pad / width
        right_tc = 1 - right_pad / width
        top_tc = top_pad / height
        bottom_tc = 1 - bottom_pad / height
        if image.orientation in [
            ExifOrientation.FLIP_HORIZONTAL_ROTATE_90_CCW,
            ExifOrientation.ROTATE_90_CW,
            ExifOrientation.FLIP_HORIZONTAL_ROTATE_90_CW,
            ExifOrientation.ROTATE_90_CCW,
        ]:
            # swap upper right and lower left
            self.vertexes = numpy.array(
                [
                    # omp_x, omp_y, txc_x, txc_y
                    [left_omp, top_omp, left_tc, top_tc],  # upper left
                    [left_omp, bottom_omp, right_tc, top_tc],  # lower left
                    [right_omp, top_omp, left_tc, bottom_tc],  # upper right
                    [right_omp, bottom_omp, right_tc, bottom_tc],  # lower right
                ],
                dtype=numpy.float32,
            ).flatten()
        else:
            self.vertexes = numpy.array(
                [
                    # omp_x, omp_y, txc_x, txc_y
                    [left_omp, top_omp, left_tc, top_tc],  # upper left
                    [left_omp, bottom_omp, left_tc, bottom_tc],  # lower left
                    [right_omp, top_omp, right_tc, top_tc],  # upper right
                    [right_omp, bottom_omp, right_tc, bottom_tc],  # lower right
                ],
                dtype=numpy.float32,
            ).flatten()
        self.texture_id = None
        self.load_sync = None
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        iw, ih = image.size_raw
        self._tile_X_img = numpy.array([
            [iw / width, 0, left_pad / width - left / width],
            [0, ih / height, top_pad / height - top / height],
            [0, 0, 1],
        ], dtype=numpy.float32)

    def initialize_gl(self):
        self.vbo = GL.glGenBuffers(1)  # noqa
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, len(self.vertexes) * sizeof(c_float), self.vertexes, GL.GL_STATIC_DRAW)
        self.texture_id = GL.glGenTextures(1)  # noqa
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        # Show monochrome images as gray, not red
        if self.internal_format == GL.GL_RED:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
        # Anisotropic filtering
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)  # noqa
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)
        # TODO: use preferred internal format in image data...
        # row stride required for horizontal tiling
        iw, ih = self.image.size_raw
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, iw)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, self.left)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, self.top)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            self.internal_format,
            self.width,
            self.height,
            0,
            self.tex_format,
            self.data_type,
            self.image.array,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        # TODO: test and debug 360 boundary conditions with tiled image
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        # Restore normal unpack settings
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, 0)
        self.load_sync = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
        GL.glFlush()

    def is_ready(self) -> bool:
        if self.load_sync is None:
            return False
        load_status = GL.glGetSynciv(self.load_sync, GL.GL_SYNC_STATUS, 1)[1]  # noqa
        return load_status == GL.GL_SIGNALED

    def is_ready_for_display(self) -> bool:
        if self.load_sync is None:
            return False
        status = GL.glClientWaitSync(
            self.load_sync,
            GL.GL_SYNC_FLUSH_COMMANDS_BIT,
            0,
        )
        return status in (GL.GL_ALREADY_SIGNALED, GL.GL_CONDITION_SATISFIED)

    def paint_gl(self) -> bool:
        if not self.is_ready_for_display():
            return False
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        # VAO must be created here, in the render thread
        if self.vao is None:
            self.vao = GL.glGenVertexArrays(1)  # noqa
            GL.glBindVertexArray(self.vao)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
            f_size = sizeof(c_float)
            GL.glVertexAttribPointer(  # normalized image coordinates
                1,  # attribute index
                2,  # size (#components)
                GL.GL_FLOAT,  # type
                False,  # normalized
                f_size * 4,  # stride (bytes)
                cast(0 * f_size, c_void_p),  # pointer offset
            )
            GL.glEnableVertexAttribArray(1)
            GL.glVertexAttribPointer(  # texture coordinates
                2,  # attribute index
                2,  # size (#components)
                GL.GL_FLOAT,  # type
                False,  # normalized
                f_size * 4,  # stride (bytes)
                cast(2 * f_size, c_void_p),  # pointer offset
            )
            GL.glEnableVertexAttribArray(2)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)  # Full screen quad
        logger.debug("Done rendering texture")
        return True

    @property
    def tile_X_img(self) -> NDArray[numpy.floating]:
        return self._tile_X_img


def omp_for_rmp(rmp: tuple[int, int], size_rmp: tuple[int, int], orientation: ExifOrientation) -> tuple[int, int]:
    omp_x_rmp = numpy.eye(3, dtype=numpy.int32)  # default transform is identity
    w, h = size_rmp

    if orientation == ExifOrientation.FLIP_HORIZONTAL:  # 2
        omp_x_rmp = numpy.array([
            [-1, 0, w],
            [0, +1, 0],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.ROTATE_180:  # 3
        omp_x_rmp = numpy.array([
            [-1, 0, w],
            [0, -1, h],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.FLIP_VERTICAL:  # 4
        omp_x_rmp = numpy.array([
            [+1, 0, 0],
            [0, -1, h],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.FLIP_HORIZONTAL_ROTATE_90_CCW:  # 5
        omp_x_rmp = numpy.array([
            [0, +1, 0],
            [+1, 0, 0],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.ROTATE_90_CW:  # 6
        omp_x_rmp = numpy.array([
            [0, -1, h],
            [+1, 0, 0],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.FLIP_HORIZONTAL_ROTATE_90_CW:  # 7
        omp_x_rmp = numpy.array([
            [0, -1, h],
            [-1, 0, w],
            [0, 0, +1],
        ], dtype=numpy.int32)
    elif orientation == ExifOrientation.ROTATE_90_CCW:  # 8
        omp_x_rmp = numpy.array([
            [0, +1, 0],
            [-1, 0, w],
            [0, 0, +1],
        ], dtype=numpy.int32)

    result = omp_x_rmp @ (*rmp, 1)
    assert result[2] == 1
    assert result[0] >= 0
    assert result[1] >= 0
    assert result[0] <= max(w, h)
    assert result[1] <= max(w, h)
    return int(result[0]), int(result[1])
