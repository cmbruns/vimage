import abc
import pkg_resources

from OpenGL import GL
from OpenGL.GL.shaders import compileShader
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT

from vmg.state import ViewState


class IImageShader(abc.ABC):
    @abc.abstractmethod
    def initialize_gl(self) -> None:
        pass

    @abc.abstractmethod
    def paint_gl(self, state: ViewState) -> None:
        pass


class RectangularShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.window_size_location = None
        self.image_center_img_location = None
        self.pixelFilter_location = None
        self.raw_rot_omp_location = None
        self.sel_rect_omp_location = None
        self.background_color_location = None
        self.background_color = [0.5, 0.5, 0.5, 0.5]

    def initialize_gl(self) -> None:
        vertex_shader = compileShader(pkg_resources.resource_string(
            "vmg", "image.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(
            pkg_resources.resource_string("vmg", "shared.frag") +
            pkg_resources.resource_string("vmg", "image.frag"),
            GL.GL_FRAGMENT_SHADER)
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.image_center_img_location = GL.glGetUniformLocation(self.shader, "image_center_img")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")
        self.raw_rot_omp_location = GL.glGetUniformLocation(self.shader, "raw_rot_omp")
        self.sel_rect_omp_location = GL.glGetUniformLocation(self.shader, "sel_rect_omp")
        self.background_color_location = GL.glGetUniformLocation(self.shader, "background_color")

    def paint_gl(self, state: ViewState) -> None:
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.zoom)
        GL.glUniform2i(self.window_size_location, *state.window_size)
        GL.glUniform2f(self.image_center_img_location, *state.center_rel)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniform4i(self.sel_rect_omp_location, *state.sel_rect.left_top_right_bottom)
        GL.glUniform4f(self.background_color_location, *self.background_color)
        GL.glUniformMatrix2fv(self.raw_rot_omp_location, 1, True, state.raw_rot_omp)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


class SphericalShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.pixelFilter_location = None
        self.ont_rot_obq_location = None
        self.raw_rot_ont_location = None
        self.window_size_location = None
        self.projection_location = None

    def initialize_gl(self) -> None:
        vertex_shader = compileShader(pkg_resources.resource_string(
            "vmg", "sphere.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(
            pkg_resources.resource_string("vmg", "shared.frag") +
            pkg_resources.resource_string("vmg", "sphere.frag"),
            GL.GL_FRAGMENT_SHADER)
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")
        self.ont_rot_obq_location = GL.glGetUniformLocation(self.shader, "ont_rot_obq")
        self.raw_rot_ont_location = GL.glGetUniformLocation(self.shader, "raw_rot_ont")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.projection_location = GL.glGetUniformLocation(self.shader, "projection")

    def paint_gl(self, state: ViewState) -> None:
        # both nearest and catmull-rom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)

        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.zoom)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix3fv(self.ont_rot_obq_location, 1, True, state.ont_rot_obq)
        GL.glUniformMatrix3fv(self.raw_rot_ont_location, 1, True, state.raw_rot_ont)
        GL.glUniform2i(self.window_size_location, *state.window_size)
        GL.glUniform1i(self.projection_location, state.projection.value)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
