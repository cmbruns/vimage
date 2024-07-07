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


class Texture(object):
    def __init__(
            self,
            channel_count: int,
            size: Tuple[GLint, GLint],
            data_type: GLenum,
            data=None,
            tex_format: Optional[GLenum] = None,
    ):
        self.size = size
        self.data = data
        self.internal_format = internal_format_for_channel_count[channel_count]
        self.tex_format = tex_format
        if self.tex_format is None:
            self.tex_format = self.internal_format
        self.data_type = data_type
        self.texture_id = None

    def bind_gl(self) -> None:
        if self.texture_id is None:
            self.upload_gl()
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)

    @staticmethod
    def from_numpy(array, tex_format=None) -> "Texture":
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
        )

    def upload_gl(self) -> None:
        max_size = GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE)
        if self.size[0] > max_size or self.size[1] > max_size:
            raise ValueError(f"Texture is too large for OpenGL; max size = {max_size}; texture size = {self.size}")  # TODO: tiled implementation
        assert self.texture_id is None
        self.texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)  # for equirectangular
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)  # for equirectangular
        # Show monochrome images as gray, not red
        if self.internal_format == GL.GL_RED:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            self.internal_format,
            self.size[0],
            self.size[1],
            0,
            self.tex_format,
            self.data_type,
            self.data,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
