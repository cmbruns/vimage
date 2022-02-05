import abc
import math
import pkg_resources

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileShader

from vmg.pixel_filter import PixelFilter


class IViewState(abc.ABC):
    @abc.abstractmethod
    def drag_relative(self, dx, dy, gl_widget):
        pass

    @abc.abstractmethod
    def reset(self):
        pass

    @abc.abstractmethod
    def zoom_relative(self, zoom_factor: float, zoom_center, gl_widget):
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
        self.image_center = [0.5, 0.5]
        self.window_zoom = 1.0
        self.pixel_filter = PixelFilter.CATMULL_ROM

    def clamp_center(self):
        # Keep the center point on the actual image itself
        self.image_center[0] = max(0.0, self.image_center[0])
        self.image_center[1] = max(0.0, self.image_center[1])
        self.image_center[0] = min(1.0, self.image_center[0])
        self.image_center[1] = min(1.0, self.image_center[1])
        z = self.window_zoom
        if z <= 1:
            self.image_center[0] = 0.5
            self.image_center[1] = 0.5
        else:
            self.image_center[0] = min(self.image_center[0], 1 - 0.5 / z)
            self.image_center[0] = max(self.image_center[0], 0.5 / z)
            self.image_center[1] = min(self.image_center[1], 1 - 0.5 / z)
            self.image_center[1] = max(self.image_center[1], 0.5 / z)

    def drag_relative(self, dx, dy, gl_widget):
        x_scale = -gl_widget.width() * self.window_zoom
        y_scale = -gl_widget.height() * self.window_zoom
        ratio_ratio = gl_widget.width() * gl_widget.image.shape[0] / (gl_widget.height() * gl_widget.image.shape[1])
        if ratio_ratio > 1:
            x_scale /= ratio_ratio
        else:
            y_scale *= ratio_ratio
        self.image_center[0] += dx / x_scale
        self.image_center[1] += dy / y_scale
        self.clamp_center()

    def image_for_window(self, wpos, gl_widget):
        x_scale = y_scale = self.window_zoom
        ratio_ratio = gl_widget.width() * gl_widget.image.shape[0] / (gl_widget.height() * gl_widget.image.shape[1])
        if ratio_ratio > 1:
            x_scale /= ratio_ratio
        else:
            y_scale *= ratio_ratio
        wx = (wpos.x() - gl_widget.width() / 2) / gl_widget.width() / x_scale
        wy = (wpos.y() - gl_widget.height() / 2) / gl_widget.height() / y_scale
        return wx, wy

    def reset(self):
        self.window_zoom = 1.0
        self.image_center = [0.5, 0.5]

    def zoom_relative(self, zoom_factor: float, zoom_center, gl_widget):
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
            self.image_center[0] -= dx
            self.image_center[1] -= dy
        # Limit zoom-out because you never need more than twice the image dimension to move around
        self.window_zoom = max(1.0, self.window_zoom)
        self.clamp_center()


class SphericalViewState(IViewState):
    def __init__(self):
        self.image_rotation = numpy.identity(3, dtype=numpy.float32)
        self.pitch = 0  # radians
        self.yaw = 0  # radians
        self.window_zoom = 1.0
        self.pixel_filter = PixelFilter.CATMULL_ROM

    def clamp(self):
        self.pitch = min(self.pitch, math.pi / 2)
        self.pitch = max(self.pitch, -math.pi / 2)
        self.window_zoom = max(self.window_zoom, 0.05)

    def drag_relative(self, dx, dy, gl_widget):
        self.yaw += dx / gl_widget.width() / self.window_zoom
        c = math.cos(self.yaw)
        s = math.sin(self.yaw)
        m1 = numpy.array([
            [c, 0, s],
            [0, 1, 0],
            [-s, 0, c],
        ], dtype=numpy.float32)
        self.pitch += dy / gl_widget.height() / self.window_zoom
        self.clamp()
        c = math.cos(self.pitch)
        s = math.sin(self.pitch)
        m2 = numpy.array([
            [1, 0, 0],
            [0, c, -s],
            [0, s, c],
        ], dtype=numpy.float32)
        self.image_rotation = m1 @ m2
        # print(roty, m)

    def image_for_window(self, wpos, gl_widget):
        x_scale = y_scale = self.window_zoom
        wx = (wpos.x() - gl_widget.width() / 2) / gl_widget.width() / x_scale
        wy = (wpos.y() - gl_widget.height() / 2) / gl_widget.height() / y_scale
        # https://en.wikipedia.org/wiki/Stereographic_projection
        denom = 1 + wx * wx + wy * wy
        x = 2 * wx / denom
        y = 2 * wy / denom
        z = (denom - 2) / denom
        longitude = math.atan2(z, x)
        latitude = math.asin(y)
        c = 1.0 / math.pi
        ix, iy = longitude * c / 2, latitude * c
        print(ix, iy)
        return ix, iy

    def reset(self):
        self.image_rotation = numpy.identity(3, dtype=numpy.float32)
        self.pitch = 0
        self.yaw = 0
        self.window_zoom = 1.0

    def zoom_relative(self, zoom_factor: float, zoom_center, gl_widget):
        new_zoom = self.window_zoom * zoom_factor
        self.window_zoom = new_zoom
        self.clamp()
        # TODO: keep center


class RectangularShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.window_size_location = None
        self.image_center_location = None
        self.pixelFilter_location = None

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
        self.image_center_location = GL.glGetUniformLocation(self.shader, "image_center")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")

    def paint_gl(self, state, gl_widget) -> None:
        # both nearest and catrom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.window_zoom)
        GL.glUniform2i(self.window_size_location, gl_widget.width(), gl_widget.height())
        GL.glUniform2f(self.image_center_location, *state.image_center)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


class SphericalShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.pixelFilter_location = None
        self.rotation_location = None
        self.window_size_location = None

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
        self.rotation_location = GL.glGetUniformLocation(self.shader, "rotation")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")

    def paint_gl(self, state, gl_widget) -> None:
        # both nearest and catrom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.window_zoom)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix3fv(self.rotation_location, 1, False, state.image_rotation)
        GL.glUniform2i(self.window_size_location, gl_widget.width(), gl_widget.height())
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
