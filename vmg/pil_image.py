"""
Intended as partial Replacement for ImageData, Texture
"""

from ctypes import c_float, c_uint8, c_void_p, cast, sizeof
import enum
import json
import logging
from OpenGL.GL.shaders import compileProgram, compileShader
from math import cos, radians, sin, degrees
from typing import Iterator, Optional

import exiftool
import numpy
from numpy.typing import NDArray
from OpenGL import GL
from OpenGL.GL.EXT.texture_filter_anisotropic import (
    GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT,
    GL_TEXTURE_MAX_ANISOTROPY_EXT,
)
import PIL
from PIL import ExifTags, Image
from PySide6 import QtCore
import tifffile

from vmg.exif_orientation import ExifOrientation
from vmg.frame import DimensionsOmp
from vmg.input_format import InputFormat
from vmg.interfaces import ImageLike, TileLike
from vmg.photometric_scale import PhotometricScale
from vmg.resources import resource_string
from vmg.shader import Sampler2DUniform, ViewerUniforms, PanoUniforms, FisheyeUniforms

logger = logging.getLogger(__name__)
GLenum = int
GLint = int


TILE_SIZE = 512


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


class ImageSignaller(QtCore.QObject):
    progress_changed = QtCore.Signal(int, ImageLike)
    image_displayed = QtCore.Signal(ImageLike)


class BasicImageLike(ImageLike):
    def __init__(self):
        self._array = numpy.eye(1)
        self._file_name: str = ""
        self._tiles: list[TileLike] = []
        self.sq = ImageSignaller()
        self.load_progress = LoadProgress.NONE
        # Reasonable defaults
        self.initial_heading_degrees = 0.0
        self.initial_pitch_degrees = 0.0
        self.initial_roll_degrees = 0.0
        self._input_format = InputFormat.STANDARD_PHOTO
        self._photometric_scale = PhotometricScale.SRGB
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self._size_raw = (0, 0)
        self._size_omp = DimensionsOmp(0, 0)
        self._orientation = ExifOrientation.ROTATE_0

    @property
    def array(self) -> NDArray:
        return self._array

    @property
    def file_name(self) -> Optional[str]:
        return self._file_name

    @property
    def input_format(self) -> InputFormat:
        return self._input_format

    @input_format.setter
    def input_format(self, input_format: InputFormat) -> None:
        self._input_format = input_format

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

    def paint_gl(self, program, view_state) -> None:
        is_complete = True  # start optimistic
        for tile in self.tiles():
            GL.glUniformMatrix3fv(program.tile_X_img_location, 1, True, tile.tile_X_img)
            GL.glUniform4f(program.uv_bounds_location, *tile.uv_bounds)
            if not tile.paint_gl(view_state):
                is_complete = False
            if is_complete and self.load_progress != LoadProgress.DISPLAYED:
                self.load_progress = LoadProgress.DISPLAYED
                self.sq.image_displayed.emit(self)  # noqa
            # break  # just one tile for testing

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
        self.sq.progress_changed.emit(2, self)  # noqa
        self.load_pil_metadata(pil_image)
        # self.metadata = load_metadata(file_name)
        # Create numpy array of image
        self.sq.progress_changed.emit(15, self)  # noqa
        # TODO: create a palette shader to avoid munging pixels here
        if pil_image.mode in ["P",]:  # Palette image
            pil_image = pil_image.convert("RGBA")
        self._array = numpy.array(pil_image)
        self.pil_image = pil_image  # TODO: MainWindow needs refactor

    def initialize_gl(self) -> None:
        """
        Construct tiles to be rendered
        Call from loading thread with OpenGL context current
        """
        max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)  # noqa
        assert max_texture_size >= TILE_SIZE
        # Loop over tiles
        w, h = self.size_raw  # TODO: raw or logical?
        channel_count = 1
        if len(self.array.shape) > 2:
            channel_count = self.array.shape[2]
        internal_format = internal_format_for_channel_count[channel_count]
        tex_format = internal_format  # TODO: BGR, GL_RGB16 etc.
        data_type = gl_type_for_numpy_dtype[self.array.dtype]
        debug = False
        if debug:
            # Set rightmost 4 columns green for testing.
            arr = self.array
            arr[:, -4:, 0] = 0  # R
            arr[:, -4:, 1] = 255  # G
            arr[:, -4:, 2] = 0  # B
            # Left 4 columns red
            arr = self.array
            arr[:, :4, 0] = 255  # R
            arr[:, :4, 1] = 0  # G
            arr[:, :4, 2] = 0  # B
            # Top 4 rows blue
            arr[:4, :, 0] = 0  # R
            arr[:4, :, 1] = 0  # G
            arr[:4, :, 2] = 255  # B
        # pad tiles by 2 pixels so cubic interpolation is seamless
        PAD = 2
        top = 0
        top_pad = 0
        while top < h:
            # determine height
            height = min(TILE_SIZE, h - top)
            # determine bottom_pad
            if top + TILE_SIZE >= h:
                bottom_pad = 0
            else:
                bottom_pad = min(PAD, h - top - TILE_SIZE)
            left = 0
            left_pad = 0
            while left < w:
                # determine width
                width = min(TILE_SIZE, w - left)
                # determine right pad
                if left + TILE_SIZE >= w:
                    right_pad = 0
                else:
                    right_pad = min(PAD, w - left - TILE_SIZE)
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
                # advance
                left += TILE_SIZE
                left_pad = PAD
            top += TILE_SIZE
            top_pad = PAD

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
        # All panos we know about have a 2:1 aspect ratio
        if w != h * 2:
            self._input_format = InputFormat.STANDARD_PHOTO
        elif model == "sm-c200" and ((w, h) == (7776, 3888) or (w, h) == (5792, 2896)):
            # 2016 Gear 360 raw image is dual fisheye
            self._input_format = InputFormat.DUAL_FISHEYE
        elif model.startswith("ricoh theta"):
            self._input_format = InputFormat.EQUIRECTANGULAR
            # TODO theta Z1 raw
        elif model.startswith("qjxj01fj"):  # Xiaomi misphere
            # Raw dual fisheye is a particular size
            if (w, h) != (6912, 3456):
                self._input_format = InputFormat.EQUIRECTANGULAR
            else:
                # TODO: could be equirect or fisheye. There is no metadata way to be sure.
                # equirect is least surprise, more discoverable than the other way around
                # if we had a RAW image (other image type) dual fisheye would be the answer
                self._input_format = InputFormat.EQUIRECTANGULAR
        else:
            self._input_format = InputFormat.EQUIRECTANGULAR  # TODO: setting?
        # raw_rot_ont  panorama camera orientation
        try:
            desc = xmp["xmpmeta"]["RDF"]["Description"]
            # Normalize to a list
            if isinstance(desc, dict):
                desc_list = [desc]
            else:
                desc_list = desc
            is_pano: Optional[bool] = None  # don't know yet
            pose_heading = 0.0
            pose_pitch = 0.0
            pose_roll = 0.0
            initial_heading = 0.0
            initial_pitch = 0.0
            initial_roll = 0.0
            for d in desc_list:
                if "PoseHeadingDegrees" in d:
                    pose_heading = radians(float(d["PoseHeadingDegrees"]))
                    is_pano = True
                if "PosePitchDegrees" in d:
                    pose_pitch = radians(float(d["PosePitchDegrees"]))
                    is_pano = True
                if "PoseRollDegrees" in d:
                    pose_roll = radians(float(d["PoseRollDegrees"]))
                    is_pano = True
                if "InitialViewHeadingDegrees" in d:
                    self.initial_heading_degrees = float(d["InitialViewHeadingDegrees"])
                    is_pano = True
                if "InitialViewPitchDegrees" in d:
                    self.initial_pitch_degrees = float(d["InitialViewPitchDegrees"])
                    is_pano = True
                if "InitialViewRollDegrees" in d:
                    self.initial_roll_degrees = float(d["InitialViewRollDegrees"])
                    is_pano = True
            Use360PanoReferenceConvention = False
            if Use360PanoReferenceConvention:
                pose_roll = -pose_roll
            if pose_heading != 0 or pose_pitch != 0 or pose_roll != 0:
                logger.info(f"Pose heading, pitch, roll = ({degrees(pose_heading)}, {degrees(pose_pitch)}, {degrees(pose_roll)})")
            # TODO: use new frame shorthands everywhere
            # https://github.com/cmbruns/vimage/issues/74
            # Photographer's camera pose
            pcm_rot_geo = numpy.array([
                [cos(pose_roll), -sin(pose_roll), 0],
                [sin(pose_roll), cos(pose_roll), 0],
                [0, 0, 1],
            ], dtype=numpy.float32)
            pcm_rot_geo = pcm_rot_geo @ [
                [1, 0, 0],
                [0, cos(pose_pitch), sin(pose_pitch)],
                [0, -sin(pose_pitch), cos(pose_pitch)],
            ]
            pcm_rot_geo = pcm_rot_geo @ [
                [cos(pose_heading), 0, sin(pose_heading)],
                [0, 1, 0],
                [-sin(pose_heading), 0, cos(pose_heading)],
            ]
            # Initial View
            # TODO incorporate IVW into pipeline separate from GEO
            self._raw_rot_ont = pcm_rot_geo
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
        self.padded_width = width + left_pad + right_pad
        self.padded_height = height + top_pad + bottom_pad
        # Convert to oriented image pixel coordinates (omp)
        left_rmp = left
        right_rmp = left_rmp + width
        top_rmp = top
        bottom_rmp = top_rmp + height
        left_omp, top_omp = omp_for_rmp((left_rmp, top_rmp), image.size_raw, image.orientation)
        right_omp, bottom_omp = omp_for_rmp((right_rmp, bottom_rmp), image.size_raw, image.orientation)
        left_tc = left_pad / self.padded_width
        right_tc = 1 - right_pad / self.padded_width
        top_tc = top_pad / self.padded_height
        bottom_tc = 1 - bottom_pad / self.padded_height
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
        self.left_pad = left_pad
        self.right_pad = right_pad
        self.top_pad = top_pad
        self.height = height
        iw, ih = image.size_raw
        self._tile_X_img = numpy.array([
            [iw / self.padded_width, 0, -(left - left_pad)/self.padded_width],
            [0, ih / self.padded_height, -(top - top_pad)/self.padded_height],
            [0, 0, 1],
        ], dtype=numpy.float32)
        self.uv_bounds = (  # // (u_min, v_min, u_max, v_max)
            left_pad / self.padded_width,
            top_pad / self.padded_height,
            (left_pad + width) / self.padded_width,
            (top_pad + height) / self.padded_height)
        self.boundary_ebo = None

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
        # TODO: use preferred internal format in image data...
        # row stride required for horizontal tiling
        iw, ih = self.image.size_raw
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, iw)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, self.left - self.left_pad)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, self.top - self.top_pad)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            self.internal_format,
            self.padded_width,
            self.padded_height,
            0,
            self.tex_format,
            self.data_type,
            self.image.array,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        # Anisotropic filtering
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)  # noqa
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        # TODO: test and debug 360 boundary conditions with tiled image
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        # Restore normal unpack settings
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, 0)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, 0)

        # Tile boundaries
        self.boundary_ebo = GL.glGenBuffers(1)  # noqa
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.boundary_ebo)
        indices = numpy.array([
            0, 1, 3, 2,
        ], dtype=numpy.uint32)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)
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

    def paint_gl(self, view_state) -> bool:
        if not self.is_ready_for_display():
            return False
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        # Debuggable texture parameters
        # Anisotropic filtering
        if view_state.anisotropic_filtering:
            aniso = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        else:
            aniso = 1
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, aniso)
        #
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, view_state.texture_wrap)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, view_state.texture_wrap)
        #
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
        outlines_only = False
        if outlines_only:
            self.paint_tile_boundary()
        else:
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)  # Full screen quad
        return True

    def paint_boundary(self):
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.boundary_ebo)
        GL.glDrawElements(GL.GL_LINE_LOOP, 4, GL.GL_UNSIGNED_INT, None)

    @property
    def tile_X_img(self) -> NDArray[numpy.floating]:
        return self._tile_X_img


class DngImage(BasicImageLike):
    def __init__(self, file_name: str):
        super().__init__()
        with tifffile.TiffFile(file_name) as dng:
            page = dng.pages[0]
            self._file_name = file_name
            self.sq.progress_changed.emit(2, self)  # noqa
            self.load_dng_metadata(dng)
            self._array = page.asarray()
        self.bayer_array = self._array
        h, w = self.bayer_array.shape
        self._size_raw = (w, h)
        self._size_omp = DimensionsOmp(w, h)  # For now...
        if self.bayer_array.dtype != numpy.uint16:
            raise Exception(f"Unexpected dtype {self.bayer_array.dtype}")
        assert len(self.bayer_array.shape) == 2
        #
        self.pil_image = Image.fromarray(self.bayer_array)
        # TODO metadata
        self._photometric_scale = PhotometricScale.LINEAR

    def initialize_gl(self) -> None:
        """
        Construct tiles to be rendered
        Call from loading thread with OpenGL context current
        """
        max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)  # noqa
        assert max_texture_size >= TILE_SIZE
        # Loop over tiles
        h, w = self.bayer_array.shape
        # Bayer image is structurally monochrome
        internal_format = GL.GL_RED
        assert self.bayer_array.dtype == numpy.uint16
        tex_format = GL.GL_R16
        data_type = GL.GL_UNSIGNED_SHORT
        # pad tiles by 2 pixels so cubic interpolation is seamless
        PAD = 2
        top = 0
        top_pad = 0
        while top < h:
            # determine height
            height = min(TILE_SIZE, h - top)
            # determine bottom_pad
            if top + TILE_SIZE >= h:
                bottom_pad = 0
            else:
                bottom_pad = min(PAD, h - top - TILE_SIZE)
            left = 0
            left_pad = 0
            while left < w:
                # determine width
                width = min(TILE_SIZE, w - left)
                # determine right pad
                if left + TILE_SIZE >= w:
                    right_pad = 0
                else:
                    right_pad = min(PAD, w - left - TILE_SIZE)
                tile = DngTile(
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
                # advance
                left += TILE_SIZE
                left_pad = PAD
            top += TILE_SIZE
            top_pad = PAD

    def load_dng_metadata(self, dng: tifffile.TiffFile):
        pass

    def paint_gl(self, program, tile_X_img_location: GLint = -1, uv_bounds_location: GLint = -1) -> None:
        is_complete = True  # start optimistic
        for tile in self.tiles():
            GL.glUniformMatrix3fv(program.tile_X_img_location, 1, True, tile.tile_X_img)
            GL.glUniform4f(program.uv_bounds_location, *tile.uv_bounds)
            program.uDemosaicTile.set(1, tile.demosaic_texture_id)
            program.uBayerTile.set(0, tile.bayer_texture_id)
            if not tile.paint_gl():
                is_complete = False
            if is_complete and self.load_progress != LoadProgress.DISPLAYED:
                self.load_progress = LoadProgress.DISPLAYED
                self.sq.image_displayed.emit(self)  # noqa
            # break  # just one tile for testing


class DngTile(Tile):
    # Loader thread resources:
    demosaic_framebuffer = None
    demosaic_program = None
    demosaic_vao = None

    def __init__(
            self,
            image: DngImage,
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
        super().__init__(image=image,
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
                         data_type=data_type)
        self.bayer_texture_id = None
        self.bayer_array = image.bayer_array
        self.demosaic_texture_id = None
        self.render_vao = None

    def initialize_gl(self):
        self.vbo = GL.glGenBuffers(1)  # noqa
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, len(self.vertexes) * sizeof(c_float), self.vertexes, GL.GL_STATIC_DRAW)
        self.bayer_texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.bayer_texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        bayer_w, bayer_h = self.image.size_raw
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, bayer_w)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, self.left - self.left_pad)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, self.top - self.top_pad)

        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,  # base mipmap
            GL.GL_R16,  # single channel
            self.padded_width,
            self.padded_height,
            0,  # border
            GL.GL_RED,
            GL.GL_UNSIGNED_SHORT,  # 16 bit
            self.bayer_array,
        )

        # We always want literally exact texel values, and no mipmapping
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        # Make all fetches outside the texture return transparent black
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)
        GL.glTexParameterfv(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_BORDER_COLOR, [0, 0, 0, 0])
        # Fill all three channels R, G, B with the one intensity
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_R, GL.GL_RED)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_A, GL.GL_ONE)

        # Construct a second downsampled demosaic texture for zoomed out visualization
        # Theoretical mipmap level 1 size
        demosaic_w = max(1, self.padded_width // 2)
        demosaic_h = max(1, self.padded_height // 2)
        # Create framebuffer
        if self.demosaic_framebuffer is None:
            self.demosaic_framebuffer = GL.glGenFramebuffers(1)
            self.demosaic_vao = GL.glGenVertexArrays(1)
            self.demosaic_program = compileProgram(
                compileShader(
                    resource_string("vmg.glsl", "demosaic.vert"),
                    GL.GL_VERTEX_SHADER),
                compileShader(
                    resource_string("vmg.glsl", "demosaic.frag"),
                    GL.GL_FRAGMENT_SHADER),
            )
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.demosaic_framebuffer)

        # Create demosaic color texture
        self.demosaic_texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.demosaic_texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        # Allocate storage for level 0 of demosaic tile (RGB float)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,  # mip level
            GL.GL_RGBA16,  # internal format
            demosaic_w,
            demosaic_h,
            0,  # border
            GL.GL_RGBA,  # upload format
            GL.GL_UNSIGNED_SHORT,  # upload type
            None  # no initial data
        )
        # Attach texture to framebuffer
        GL.glFramebufferTexture2D(
            GL.GL_FRAMEBUFFER,
            GL.GL_COLOR_ATTACHMENT0,
            GL.GL_TEXTURE_2D,
            self.demosaic_texture_id,
            0  # mip level
        )
        # Set draw buffers
        GL.glDrawBuffers(1, [GL.GL_COLOR_ATTACHMENT0])
        # Check completeness
        status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        if status != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Framebuffer incomplete: 0x{status:X}")

        # Populate the demosaic texture
        GL.glBindVertexArray(self.demosaic_vao)
        GL.glViewport(0, 0, demosaic_w, demosaic_h)
        # Render
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.bayer_texture_id)
        GL.glUseProgram(self.demosaic_program)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

        # Generate demosaic mipmaps
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.demosaic_texture_id)
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        # We do catrom filtering in-shadero, so use GL_NEAREST for now
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        # Anisotropic filtering
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)

        # TODO: so much duplicated code
        self.boundary_ebo = GL.glGenBuffers(1)  # noqa
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.boundary_ebo)
        indices = numpy.array([
            0, 1, 3, 2,
        ], dtype=numpy.uint32)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)

        # Clean up
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self.load_sync = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
        GL.glFlush()  # macOS probably
        logger.debug("DNG demosaic complete")

    def paint_gl(self) -> bool:
        """Run in ui thread"""
        if not self.is_ready_for_display():
            return False
        if self.render_vao is None:
            self.render_vao = GL.glGenVertexArrays(1)
            self.vao = self.render_vao
            GL.glBindVertexArray(self.render_vao)
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
        assert self.render_vao is not None
        GL.glBindVertexArray(self.render_vao)
        # TODO bind textures
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)  # Tile
        return True

    def paint_boundary(self):
        GL.glBindVertexArray(self.render_vao)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.boundary_ebo)
        GL.glDrawElements(GL.GL_LINE_LOOP, 4, GL.GL_UNSIGNED_INT, None)


def load_metadata(path):
    with exiftool.ExifTool() as et:
        raw = et.execute("-j", path)
        return json.loads(raw)[0]


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
