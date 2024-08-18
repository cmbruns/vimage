from ctypes import c_float, c_void_p, cast, sizeof
import enum
import numpy
from typing import Tuple, Optional

from OpenGL import GL
from OpenGL.GL import GLint, GLenum
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT

# Number of channels
internal_format_for_channel_count = {
    1: GL.GL_RED,
    2: GL.GL_RG,
    3: GL.GL_RGB,
    4: GL.GL_RGBA,
}

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


class ExifOrientation(enum.Enum):
    """Names describe the transformation from raw to oriented"""
    UNSPECIFIED = 0
    ROTATE_0 = 1
    FLIP_HORIZONTAL = 2
    ROTATE_180 = 3
    FLIP_VERTICAL = 4
    FLIP_HORIZONTAL_ROTATE_90_CCW = 5
    ROTATE_90_CW = 6
    FLIP_HORIZONTAL_ROTATE_90_CW = 7
    ROTATE_90_CCW = 8


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


class Tile(object):
    def __init__(
            self,
            texture: "Texture",
            # portion of the image covered by this tile
            left: int,
            top: int,
            width: int,
            height: int,
            left_pad: int,
            top_pad: int,
            right_pad: int,
            bottom_pad: int,
    ):
        self.texture = texture
        self.vao = None
        self.vbo = None
        # Convert to oriented image pixel coordinates (omp)
        left_rmp = left + left_pad
        right_rmp = left + width - right_pad
        top_rmp = top + top_pad
        bottom_rmp = top + height - bottom_pad
        left_omp, top_omp = omp_for_rmp((left_rmp, top_rmp), texture.size, texture.orientation)
        right_omp, bottom_omp = omp_for_rmp((right_rmp, bottom_rmp), texture.size, texture.orientation)
        left_tc = left_pad / width
        right_tc = 1 - right_pad / width
        top_tc = top_pad / height
        bottom_tc = 1 - bottom_pad / height
        # print(
        #     f" rmp: {left_rmp},{top_rmp},{right_rmp},{bottom_rmp}"
        #     f"\n omp: {left_omp},{top_omp},{right_omp},{bottom_omp}"
        #     f"\n txc: {left_tc:.5f},{top_tc:.5f},{right_tc:.5f},{bottom_tc:.5f}"
        # )
        # TODO: understand why this is needed...
        if texture.orientation in [
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

    def initialize_gl(self, image_bytes):
        self.vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, len(self.vertexes) * sizeof(c_float), self.vertexes, GL.GL_STATIC_DRAW)
        self.texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        # Show monochrome images as gray, not red
        if self.texture.internal_format == GL.GL_RED:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
        # Anisotropic filtering
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)
        # TODO: use preferred internal format in image data...
        # row stride required for horizontal tiling
        GL.glPixelStorei(GL.GL_UNPACK_ROW_LENGTH, self.texture.width)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_PIXELS, self.left)
        GL.glPixelStorei(GL.GL_UNPACK_SKIP_ROWS, self.top)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            self.texture.internal_format,
            self.width,
            self.height,
            0,
            self.texture.tex_format,
            self.texture.data_type,
            image_bytes,
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

    def is_ready(self) -> bool:
        load_status = GL.glGetSynciv(self.load_sync, GL.GL_SYNC_STATUS, 1)[1]
        return load_status == GL.GL_SIGNALED

    def paint_gl(self):
        if not self.is_ready():
            return
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        # VAO must be created here, in the render thread
        if self.vao is None:
            self.vao = GL.glGenVertexArrays(1)
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
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


class Texture(object):
    def __init__(
            self,
            channel_count: int,
            size: Tuple[GLint, GLint],
            data_type: GLenum,
            data=None,
            tex_format: Optional[GLenum] = None,
            orientation=ExifOrientation.UNSPECIFIED,
            tile_size = 8192
    ):
        self.size = size
        self.data = data
        self.internal_format = internal_format_for_channel_count[channel_count]
        self.tex_format = tex_format
        if self.tex_format is None:
            self.tex_format = self.internal_format
        self.data_type = data_type
        self.orientation = orientation
        self.tile_size = tile_size
        self.tiles = []

    def __getitem__(self, key):
        return self.tiles[key]

    def __len__(self):
        return len(self.tiles)

    @staticmethod
    def from_numpy(array, tex_format=None, orientation=ExifOrientation.UNSPECIFIED) -> "Texture":
        h, w = array.shape[:2]
        if len(array.shape) == 2:
            channel_count = 1
        else:
            channel_count = array.shape[2]
        return Texture(
            channel_count=channel_count,
            size=(w, h),
            data=array,
            tex_format=tex_format,
            data_type=gl_type_for_numpy_dtype[array.dtype],
            orientation=orientation,
        )

    @property
    def height(self):
        return self.size[1]

    def initialize_gl(self):
        tile_size = self.tile_size
        max_texture_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)
        assert max_texture_size >= tile_size
        # Loop over tiles
        top = 0
        # pad tiles by 2 pixels so cubic interpolation is seamless
        top_pad = 0
        bottom_pad = 2
        while top <= self.height:
            if top + tile_size - 4 >= self.height:  # TODO: is 4 correct here?
                bottom_pad = 0
            left = 0
            left_pad = 0
            right_pad = 2
            while left <= self.width:
                if left + tile_size - 4 >= self.width:
                    right_pad = 0
                width = min(tile_size, self.width - left)
                height = min(tile_size, self.height - top)
                # print(left, top, width, height)
                tile = Tile(
                    texture=self,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    left_pad=left_pad,
                    top_pad=top_pad,
                    right_pad=right_pad,
                    bottom_pad=bottom_pad,
                )
                self.tiles.append(tile)
                tile.initialize_gl(self.data)
                left += tile_size - 4
                left_pad = 2
            top += tile_size - 4
            top_pad = 2

    def paint_gl(self):
        for tile in self:
            tile.paint_gl()

    @property
    def width(self):
        return self.size[0]
