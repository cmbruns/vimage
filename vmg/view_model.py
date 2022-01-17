import pkg_resources

from OpenGL import GL
from OpenGL.GL.shaders import compileShader

from vmg.pixel_filter import PixelFilter


class RectangularViewModel(object):
    def __init__(self, *args, **kwargs):
        self.image_center = [0.5, 0.5]
        self.window_zoom = 1.0
        self.pixelFilter = PixelFilter.CATMULL_ROM
        #
        self.shader = None
        self.zoom_location = None
        self.window_size_location = None
        self.image_center_location = None
        self.pixelFilter_location = None

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
        print(self.image_center)
        self.clamp_center()

    def initializeGL(self) -> None:
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

    def paintGL(self, glwidget) -> None:
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, self.window_zoom)
        GL.glUniform2i(self.window_size_location, glwidget.width(), glwidget.height())
        GL.glUniform2f(self.image_center_location, *self.image_center)
        GL.glUniform1i(self.pixelFilter_location, self.pixelFilter.value)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

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
            z2 = gl_widget.image_for_window(zoom_center)  # After position
            z1 = [x * zoom_factor for x in z2]  # Before position
            dx = z2[0] - z1[0]
            dy = z2[1] - z1[1]
            self.image_center[0] -= dx
            self.image_center[1] -= dy
        # Limit zoom-out because you never need more than twice the image dimension to move around
        self.window_zoom = max(1.0, self.window_zoom)
        self.clamp_center()


class PanoSphereViewModel(object):
    pass
