import abc
import math
import pkg_resources
from typing import Tuple, Optional
from numbers import Number

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileShader
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT

from vmg.coordinate import WindowPos
from vmg.pixel_filter import PixelFilter
from vmg.projection_360 import Projection360


class IViewState(abc.ABC):
    def __init__(self):
        self.window_zoom = 1.0
        self.pixel_filter = PixelFilter.CATMULL_ROM

    @abc.abstractmethod
    def drag_relative(self, dx: int, dy: int, gl_widget):
        pass

    @abc.abstractmethod
    def image_for_window(self, p_win: WindowPos, gl_widget):
        pass

    @abc.abstractmethod
    def reset(self):
        pass

    @abc.abstractmethod
    def zoom_relative(self, zoom_factor: float, zoom_center: Optional[WindowPos], gl_widget):
        pass


class IImageShader(abc.ABC):
    @abc.abstractmethod
    def initialize_gl(self) -> None:
        pass

    @abc.abstractmethod
    def paint_gl(self, state, gl_widget) -> None:
        pass


class RectangularViewState(IViewState):
    def __init__(self):
        super().__init__()
        self.image_center_img = [0.5, 0.5]  # In GL-like oriented texture coordinates

    def clamp_center(self):
        # Keep the center point on the actual image itself
        self.image_center_img[0] = max(0.0, self.image_center_img[0])
        self.image_center_img[1] = max(0.0, self.image_center_img[1])
        self.image_center_img[0] = min(1.0, self.image_center_img[0])
        self.image_center_img[1] = min(1.0, self.image_center_img[1])
        z = self.window_zoom
        if z <= 1:
            self.image_center_img[0] = 0.5
            self.image_center_img[1] = 0.5
        else:
            self.image_center_img[0] = min(self.image_center_img[0], 1 - 0.5 / z)
            self.image_center_img[0] = max(self.image_center_img[0], 0.5 / z)
            self.image_center_img[1] = min(self.image_center_img[1], 1 - 0.5 / z)
            self.image_center_img[1] = max(self.image_center_img[1], 0.5 / z)

    def drag_relative(self, dx, dy, gl_widget):
        # Compute scales for converting window pixels to ndc coordinates
        x_scale = -gl_widget.width() * self.window_zoom
        y_scale = -gl_widget.height() * self.window_zoom
        img_height_raw, img_width_raw = gl_widget.image.shape[0:2]
        img_width_ont, img_height_ont = [abs(x) for x in (gl_widget.raw_rot_ont @ [img_width_raw, img_height_raw])]
        window_aspect = gl_widget.width() / gl_widget.height()
        image_aspect_ont = img_width_ont / img_height_ont
        ratio_ratio = window_aspect / image_aspect_ont
        if window_aspect > image_aspect_ont:
            x_scale /= ratio_ratio
        else:
            y_scale *= ratio_ratio
        self.image_center_img[0] += dx / x_scale
        self.image_center_img[1] += dy / y_scale
        self.clamp_center()

    def image_for_window(self, p_qwn: WindowPos, gl_widget):
        p_cwn = numpy.array(p_qwn) - (gl_widget.width() / 2, gl_widget.height() / 2)  # origin at center
        p_cwn[1] *= -1  # flip y
        window_aspect = gl_widget.width() / gl_widget.height()
        image_size_raw = numpy.flip(gl_widget.image.shape[0:2])
        image_size_ont = [abs(x) for x in gl_widget.raw_rot_ont.T @ image_size_raw]
        image_aspect_ont = image_size_ont[0] / image_size_ont[1]
        if window_aspect > image_aspect_ont:
            rc_scale = image_size_ont[1] / gl_widget.height() / self.window_zoom
        else:
            rc_scale = image_size_ont[0] / gl_widget.width() / self.window_zoom
        p_ont = numpy.array([
            [rc_scale, 0],
            [0, -rc_scale],
        ], dtype=numpy.float32) @ p_cwn
        p_img = p_ont / image_size_ont  # origin at center, oriented, texture coordinates
        return p_img

    def reset(self):
        self.window_zoom = 1.0
        self.image_center_img = [0.5, 0.5]

    def zoom_relative(self, zoom_factor: float, zoom_center: Optional[WindowPos], gl_widget):
        new_zoom = self.window_zoom * zoom_factor
        if new_zoom <= 1:
            zoom_factor = 1 / self.window_zoom
            new_zoom = 1
        self.window_zoom = new_zoom
        if zoom_center is not None:
            z2 = self.image_for_window(zoom_center, gl_widget)  # After position
            z1 = [x * zoom_factor for x in z2]  # Before position
            dx = z2[0] - z1[0]
            dy = z2[1] - z1[1]
            self.image_center_img[0] -= dx
            self.image_center_img[1] -= dy
        # Limit zoom-out because you never need more than twice the image dimension to move around
        self.window_zoom = max(1.0, self.window_zoom)
        self.clamp_center()


class SphericalViewState(IViewState):
    def __init__(self):
        super().__init__()
        self.view_rot_ont = numpy.identity(3, dtype=numpy.float32)
        self.view_pitch = 0.0  # radians
        self.view_yaw = 0.0  # radians
        self.projection = Projection360.STEREOGRAPHIC

    def clamp(self):
        self.view_pitch = min(self.view_pitch, math.pi / 2.0)
        self.view_pitch = max(self.view_pitch, -math.pi / 2.0)
        self.window_zoom = max(self.window_zoom, 0.05)

    def drag_relative(self, dx, dy, gl_widget):
        win_size = (gl_widget.width() + gl_widget.height()) / 2
        self.view_yaw += dx / win_size / self.window_zoom
        c = math.cos(self.view_yaw)
        s = math.sin(self.view_yaw)
        view_rot_pitch = numpy.array([
            [c, 0, s],
            [0, 1, 0],
            [-s, 0, c],
        ], dtype=numpy.float32)
        self.view_pitch += dy / win_size / self.window_zoom
        self.clamp()
        c = math.cos(self.view_pitch)
        s = math.sin(self.view_pitch)
        pitch_rot_ont = numpy.array([
            [1, 0, 0],
            [0, c, -s],
            [0, s, c],
        ], dtype=numpy.float32)
        self.view_rot_ont = view_rot_pitch @ pitch_rot_ont

    def image_for_window(self, p_win: WindowPos, gl_widget) -> Tuple[Number, Number]:
        x_scale = y_scale = self.window_zoom
        wx = (p_win[0] - gl_widget.width() / 2) / gl_widget.width() / x_scale
        wy = (p_win[1] - gl_widget.height() / 2) / gl_widget.height() / y_scale
        # https://en.wikipedia.org/wiki/Stereographic_projection
        denominator = 1 + wx * wx + wy * wy
        x = 2 * wx / denominator
        y = 2 * wy / denominator
        z = (denominator - 2) / denominator
        longitude = math.atan2(z, x)
        latitude = math.asin(y)
        c = 1.0 / math.pi
        ix, iy = longitude * c / 2, latitude * c
        return ix, iy

    def reset(self):
        self.view_rot_ont = numpy.identity(3, dtype=numpy.float32)
        self.view_pitch = 0
        self.view_yaw = 0
        self.window_zoom = 1.0

    def zoom_relative(self, zoom_factor: float, zoom_center: Optional[WindowPos], gl_widget):
        new_zoom = self.window_zoom * zoom_factor
        self.window_zoom = new_zoom
        self.clamp()
        # TODO: keep center


class RectangularShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.window_size_location = None
        self.image_center_img_location = None
        self.pixelFilter_location = None
        self.raw_rot_ont_location = None

    def initialize_gl(self) -> None:
        vertex_shader = compileShader(pkg_resources.resource_string(
            "vmg", "image.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(pkg_resources.resource_string(
            "vmg", "image.frag", ), GL.GL_FRAGMENT_SHADER)
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.image_center_img_location = GL.glGetUniformLocation(self.shader, "image_center_img")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")
        self.raw_rot_ont_location = GL.glGetUniformLocation(self.shader, "raw_rot_ont")

    def paint_gl(self, state, gl_widget) -> None:
        # both nearest and catmull-rom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.window_zoom)
        GL.glUniform2i(self.window_size_location, gl_widget.width(), gl_widget.height())
        GL.glUniform2f(self.image_center_img_location, *state.image_center_img)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix2fv(self.raw_rot_ont_location, 1, True, gl_widget.raw_rot_ont)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


class SphericalShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.pixelFilter_location = None
        self.view_rot_ont_location = None
        self.window_size_location = None
        self.projection_location = None

    def initialize_gl(self) -> None:
        vertex_shader = compileShader(pkg_resources.resource_string(
            "vmg", "sphere.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(pkg_resources.resource_string(
            "vmg", "sphere.frag", ), GL.GL_FRAGMENT_SHADER)
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")
        self.view_rot_ont_location = GL.glGetUniformLocation(self.shader, "view_rot_ont")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.projection_location = GL.glGetUniformLocation(self.shader, "projection")

    def paint_gl(self, state, gl_widget) -> None:
        # both nearest and catmull-rom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)

        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.window_zoom)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix3fv(self.view_rot_ont_location, 1, True, state.view_rot_ont)
        GL.glUniform2i(self.window_size_location, gl_widget.width(), gl_widget.height())
        GL.glUniform1i(self.projection_location, state.projection.value)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
