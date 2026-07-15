import traceback

import abc
import logging
from math import radians
from typing import Callable, OrderedDict

from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT

from vmg.dng_texture import DngTextureAdapter
from vmg.interfaces import RenderStateLike, ImageLike
from vmg.photometric_scale import PhotometricScale
from vmg.resources import resource_string
from vmg.shader_exception import compile_shader
from vmg.texture import Tile

logger = logging.getLogger(__name__)


class IImageShader(abc.ABC):
    @abc.abstractmethod
    def initialize_gl(self) -> None:
        pass

    @abc.abstractmethod
    def paint_gl(self, state: RenderStateLike, texture) -> None:
        pass


class Uniform:
    def __init__(self, name: str, set_fn: Callable):
        self.name = name
        self.location = None
        self.set_fn = set_fn

    def get_location(self, program):
        self.location = GL.glGetUniformLocation(program, self.name)

    def set(self, *args):
        self.set_fn(self.location, *args)


class Sampler2DUniform(Uniform):
    def __init__(self, name: str):
        super().__init__(name, GL.glUniform1i)

    def set(self, unit: int, texture_id: int):
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
        GL.glUniform1i(self.location, unit)


class UniformGroup:
    def __init__(self):
        self._index = OrderedDict()

    def __getitem__(self, key):
        return self._index[key]

    def add(self, uniform):
        self._index[uniform.name] = uniform

    def get_location(self, program: int):
        for u in self._index.values():
            u.get_location(program)


class ViewerUniforms(UniformGroup):
    def __init__(self):
        super().__init__()
        self.add(Uniform("brightness", GL.glUniform1f))
        self.add(Uniform("pixelFilter", GL.glUniform1i))
        self.add(Uniform("tile_X_img", GL.glUniformMatrix3fv))

    def set(self, state: RenderStateLike, tile: Tile):
        self["brightness"].set(state.brightness)
        self["pixelFilter"].set(state.pixel_filter.value)
        self["tile_X_img"].set(1, True, tile.tile_X_img)


class PanoUniforms(UniformGroup):
    def __init__(self):
        super().__init__()
        self.add(Uniform("window_size", GL.glUniform2i))
        self.add(Uniform("window_zoom", GL.glUniform1f))
        self.add(Uniform("display_projection", GL.glUniform1i))
        self.add(Uniform("ont_rot_obq", GL.glUniformMatrix3fv))
        self.add(Uniform("raw_rot_ont", GL.glUniformMatrix3fv))

    def set(self, state: RenderStateLike):
        self["window_size"].set(*[int(x) for x in state.window_size])
        self["window_zoom"].set(state.zoom)
        self["display_projection"].set(state.display_projection.value)
        self["ont_rot_obq"].set(1, True, state.ont_rot_obq)
        self["raw_rot_ont"].set(1, True, state.raw_rot_ont)


class FisheyeUniforms(UniformGroup):
    def __init__(self):
        super().__init__()
        self.add(Uniform("df_fov_radians", GL.glUniform1f))
        self.add(Uniform("df_lens_rot_radians", GL.glUniform1f))


class DemosaicShader(IImageShader):
    def __init__(self):
        self.program = None

    def initialize_gl(self) -> None:
        try:
            self.program = compileProgram(
                compileShader(
                    resource_string("vmg.glsl", "demosaic.vert"),
                    GL.GL_VERTEX_SHADER),
                compileShader(
                    resource_string("vmg.glsl", "demosaic.frag"),
                    GL.GL_FRAGMENT_SHADER),
            )
        except BaseException as exc:
            logger.error(exc)
            raise

    def paint_gl(self, state: RenderStateLike, texture) -> None:
        GL.glUseProgram(self.program)


class RectangularTileShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.ndc_x_omp_location = None
        self.pixelFilter_location = None
        self.sel_rect_omp_location = None
        self.background_color_location = None
        self.omp_scale_qwn_location = None
        self.tile_X_img_location = -1
        self.uv_bounds_location = -1
        self.brightness = Uniform("brightness", GL.glUniform1f)
        self.input_is_linear = Uniform("input_is_linear", GL.glUniform1i)
        self.background_color = [0.5, 0.5, 0.5, 0.5]
        self.box_shader = SelectionBoxShader()
        self.tile_boundary_shader = TileBoundaryShader()

    def initialize_gl(self) -> None:
        try:
            vertex_shader = compileShader(resource_string(
                "vmg.glsl", "tile_rect.vert", ), GL.GL_VERTEX_SHADER)
            fragment_shader = compile_shader("vmg.glsl", [
                "shared.frag", "tile_rect.frag"], GL.GL_FRAGMENT_SHADER)
            self.shader = GL.glCreateProgram()
            GL.glAttachShader(self.shader, vertex_shader)
            GL.glAttachShader(self.shader, fragment_shader)
            GL.glLinkProgram(self.shader)
            self.ndc_x_omp_location = GL.glGetUniformLocation(self.shader, "ndc_X_omp")
            self.sel_rect_omp_location = GL.glGetUniformLocation(self.shader, "sel_rect_omp")
            self.background_color_location = GL.glGetUniformLocation(self.shader, "background_color")
            self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixel_filter")
            self.omp_scale_qwn_location = GL.glGetUniformLocation(self.shader, "omp_scale_qwn")
            self.brightness.get_location(self.shader)
            self.input_is_linear.get_location(self.shader)
            self.box_shader.initialize_gl()
            self.tile_boundary_shader.initialize_gl()
        except BaseException as exc:
            traceback.print_exception(exc)
            raise

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        self.box_shader.paint_gl(state, image)
        if isinstance(image, DngTextureAdapter):
            image.paint_gl(state)
            return
        GL.glUseProgram(self.shader)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniform4i(self.sel_rect_omp_location, *state.sel_rect.left_top_right_bottom)
        GL.glUniform4f(self.background_color_location, *state.background_color)
        GL.glUniformMatrix3fv(self.ndc_x_omp_location, 1, True, state.ndc_xform_omp())
        GL.glUniform1f(self.omp_scale_qwn_location, state.omp_scale_qwn())
        self.brightness.set(state.brightness)
        self.input_is_linear.set(image.photometric_scale == PhotometricScale.LINEAR)
        image.paint_gl(self, state)
        if state.show_tile_boundaries:
            self.tile_boundary_shader.paint_gl(state, image)


class RectangularDngShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.ndc_x_omp_location = None
        self.pixelFilter_location = None
        self.sel_rect_omp_location = None
        self.background_color_location = None
        self.omp_scale_qwn_location = None
        self.brightness = Uniform("brightness", GL.glUniform1f)
        self.background_color = [0.5, 0.5, 0.5, 0.5]
        self.box_shader = SelectionBoxShader()
        self.uBayerTile = Sampler2DUniform("bayer_tile")
        self.uDemosaicTile = Sampler2DUniform("demosaic_tile")
        self.tile_X_img_location = -1
        self.uv_bounds_location = -1
        self.tile_boundary_shader = TileBoundaryShader()

    def initialize_gl(self) -> None:
        try:
            vertex_shader = compileShader(resource_string(
                "vmg.glsl", "tile_rect.vert",
            ), GL.GL_VERTEX_SHADER)
            fragment_shader = compile_shader(
                "vmg.glsl", [
                    "shared.frag",
                    "tile_rect_dng.frag",
                ], GL.GL_FRAGMENT_SHADER)
            self.shader = GL.glCreateProgram()
            GL.glAttachShader(self.shader, vertex_shader)
            GL.glAttachShader(self.shader, fragment_shader)
            GL.glLinkProgram(self.shader)
            self.ndc_x_omp_location = GL.glGetUniformLocation(self.shader, "ndc_X_omp")
            self.sel_rect_omp_location = GL.glGetUniformLocation(self.shader, "sel_rect_omp")
            self.background_color_location = GL.glGetUniformLocation(self.shader, "background_color")
            self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixel_filter")
            self.omp_scale_qwn_location = GL.glGetUniformLocation(self.shader, "omp_scale_qwn")
            self.brightness.get_location(self.shader)
            self.tile_X_img_location = GL.glGetUniformLocation(self.shader, "tile_X_img")
            self.uv_bounds_location = GL.glGetUniformLocation(self.shader, "uv_bounds")
            for uniform in (
                    self.uBayerTile,
                    self.uDemosaicTile,
            ):
                uniform.get_location(self.shader)
            self.box_shader.initialize_gl()
            self.tile_boundary_shader.initialize_gl()
        except BaseException as exc:
            traceback.print_exception(exc)
            raise

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        self.box_shader.paint_gl(state, image)
        GL.glUseProgram(self.shader)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniform4i(self.sel_rect_omp_location, *state.sel_rect.left_top_right_bottom)
        GL.glUniform4f(self.background_color_location, *state.background_color)
        GL.glUniformMatrix3fv(self.ndc_x_omp_location, 1, True, state.ndc_xform_omp())
        GL.glUniform1f(self.omp_scale_qwn_location, state.omp_scale_qwn())
        self.brightness.set(state.brightness)
        image.paint_gl(self)
        if state.show_tile_boundaries:
            self.tile_boundary_shader.paint_gl(state, image)


class SelectionBoxShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.ndc_x_omp_location = None
        self.sel_rect_omp_location = None
        self.background_color_location = None
        self.omp_scale_qwn_location = None

    def initialize_gl(self) -> None:
        vertex_shader = compileShader(resource_string(
            "vmg.glsl", "sel_box.vert", ), GL.GL_VERTEX_SHADER)
        fragment_shader = compileShader(
            resource_string("vmg.glsl", "shared.frag") +
            resource_string("vmg.glsl", "sel_box.frag"),
            GL.GL_FRAGMENT_SHADER)
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.ndc_x_omp_location = GL.glGetUniformLocation(self.shader, "ndc_X_omp")
        self.sel_rect_omp_location = GL.glGetUniformLocation(self.shader, "sel_rect_omp")
        self.background_color_location = GL.glGetUniformLocation(self.shader, "background_color")
        self.omp_scale_qwn_location = GL.glGetUniformLocation(self.shader, "omp_scale_qwn")

    def paint_gl(self, state: RenderStateLike, texture) -> None:
        GL.glUseProgram(self.shader)
        GL.glUniform4i(self.sel_rect_omp_location, *state.sel_rect.left_top_right_bottom)
        GL.glUniform4f(self.background_color_location, *state.background_color)
        GL.glUniformMatrix3fv(self.ndc_x_omp_location, 1, True, state.ndc_xform_omp())
        GL.glUniform1f(self.omp_scale_qwn_location, state.omp_scale_qwn())
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 10)


class SphericalShader(IImageShader):
    def __init__(self):
        self.shader = None
        self.zoom_location = None
        self.pixelFilter_location = None
        self.ont_rot_obq_location = None
        self.raw_rot_ont_location = None
        self.window_size_location = None
        self.input_format_location = None
        self.display_projection_location = None
        self.tile_X_img_location = None
        self.uv_bounds_location = None
        self.brightness = Uniform("brightness", GL.glUniform1f)
        self.input_is_linear = Uniform("input_is_linear", GL.glUniform1i)
        # TODO dual fisheye parameters should be stored per-camera or whatever
        self.df_fov_radians = radians(195.0)
        self.df_lens_rot_radians = radians(0.0)
        self.df_fov_radians_location = None
        self.df_lens_rot_radians_location = None

    def initialize_gl(self) -> None:
        try:
            vertex_shader = compileShader(resource_string(
                "vmg.glsl", "sphere.vert", ), GL.GL_VERTEX_SHADER)
            fragment_shader = compileShader(
                resource_string("vmg.glsl", "shared.frag") +
                resource_string("vmg.glsl", "sphere.frag"),
                GL.GL_FRAGMENT_SHADER)
        except BaseException as exc:
            logger.error(exc)
            raise
        self.shader = GL.glCreateProgram()
        GL.glAttachShader(self.shader, vertex_shader)
        GL.glAttachShader(self.shader, fragment_shader)
        GL.glLinkProgram(self.shader)
        self.zoom_location = GL.glGetUniformLocation(self.shader, "window_zoom")
        self.pixelFilter_location = GL.glGetUniformLocation(self.shader, "pixelFilter")
        self.ont_rot_obq_location = GL.glGetUniformLocation(self.shader, "ont_rot_obq")
        self.raw_rot_ont_location = GL.glGetUniformLocation(self.shader, "raw_rot_ont")
        self.window_size_location = GL.glGetUniformLocation(self.shader, "window_size")
        self.input_format_location = GL.glGetUniformLocation(self.shader, "input_format")
        self.display_projection_location = GL.glGetUniformLocation(self.shader, "display_projection")
        self.tile_X_img_location = GL.glGetUniformLocation(self.shader, "tile_X_img")
        self.uv_bounds_location = GL.glGetUniformLocation(self.shader, "uv_bounds")
        self.df_fov_radians_location = GL.glGetUniformLocation(self.shader, "df_fov_radians")
        self.df_lens_rot_radians_location = GL.glGetUniformLocation(self.shader, "df_lens_rot_radians")
        for u in self.brightness, self.input_is_linear:
            u.get_location(self.shader)

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        if isinstance(image, DngTextureAdapter):
            image.paint_gl(state)
            return
        # both nearest and catmull-rom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)  # noqa
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)

        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.zoom)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix3fv(self.ont_rot_obq_location, 1, True, state.ont_rot_obq)
        GL.glUniformMatrix3fv(self.raw_rot_ont_location, 1, True, image.raw_rot_ont)
        GL.glUniform2i(self.window_size_location, *[int(x) for x in state.window_size])
        GL.glUniform1i(self.input_format_location, image.input_format.value)
        GL.glUniform1i(self.display_projection_location, state.display_projection.value)
        GL.glUniform1f(self.df_fov_radians_location, self.df_fov_radians)
        GL.glUniform1f(self.df_lens_rot_radians_location, self.df_lens_rot_radians)
        self.brightness.set(state.brightness)
        self.input_is_linear.set(image.photometric_scale == PhotometricScale.LINEAR)
        image.paint_gl(self, state)


class SphericalDngShader(IImageShader):
    uBayerTile = Sampler2DUniform("bayer_tile")
    uDemosaicTile = Sampler2DUniform("demosaic_tile")
    uViewer = ViewerUniforms()
    uPano = PanoUniforms()
    uFisheye = FisheyeUniforms()

    def __init__(self):
        self.shader = None
        # TODO dual fisheye parameters should be stored per-camera or whatever
        self.df_fov_radians = radians(195.0)
        self.df_lens_rot_radians = radians(0.0)
        self.df_fov_radians_location = None
        self.df_lens_rot_radians_location = None

    def initialize_gl(self) -> None:
        self.shader = compileProgram(
            compileShader(
                resource_string("vmg.glsl", "sphere.vert"),
                GL.GL_VERTEX_SHADER),
            compileShader(
                resource_string("vmg.glsl", "shared.frag") +
                resource_string("vmg.glsl", "sphere_dng.frag"),
                GL.GL_FRAGMENT_SHADER),
        )
        for uniform in (
                self.uViewer,
                self.uPano,
                self.uFisheye,
                self.uBayerTile,
                self.uDemosaicTile,
        ):
            uniform.get_location(self.shader)

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        if isinstance(image, DngTextureAdapter):
            image.paint_gl(state)
            return
        # both nearest and catmull-rom use nearest at the moment.
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        f_largest = GL.glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)  # noqa
        GL.glTexParameterf(GL.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY_EXT, f_largest)

        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.zoom_location, state.zoom)
        GL.glUniform1i(self.pixelFilter_location, state.pixel_filter.value)
        GL.glUniformMatrix3fv(self.ont_rot_obq_location, 1, True, state.ont_rot_obq)
        GL.glUniformMatrix3fv(self.raw_rot_ont_location, 1, True, image.raw_rot_ont)
        GL.glUniform2i(self.window_size_location, *[int(x) for x in state.window_size])
        GL.glUniform1i(self.input_format_location, image.input_format.value)
        GL.glUniform1i(self.display_projection_location, state.display_projection.value)
        GL.glUniform1f(self.df_fov_radians_location, self.df_fov_radians)
        GL.glUniform1f(self.df_lens_rot_radians_location, self.df_lens_rot_radians)
        self.brightness.set(state.brightness)
        self.input_is_linear.set(image.photometric_scale == PhotometricScale.LINEAR)
        image.paint_gl(self.tile_X_img_location, self.uv_bounds_location)


class TileBoundaryShader(IImageShader):
    def __init__(self):
        self.program = None
        self.uViewport = Uniform("uViewportSize", GL.glUniform2f)
        self.ndc_X_omp = Uniform("ndc_X_omp", GL.glUniformMatrix3fv)

    def initialize_gl(self) -> None:
        self.program = compileProgram(
            compile_shader("vmg.glsl",
                           ["tile_rect.vert"], GL.GL_VERTEX_SHADER),
            compile_shader("vmg.glsl",
                           ["tile_boundary.geom"], GL.GL_GEOMETRY_SHADER),
            compile_shader("vmg.glsl",
                           ["tile_boundary.frag"], GL.GL_FRAGMENT_SHADER),
        )
        self.uViewport.get_location(self.program)
        self.ndc_X_omp.get_location(self.program)

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        GL.glUseProgram(self.program)
        self.uViewport.set(*state.window_size)
        self.ndc_X_omp.set(1, True, state.ndc_xform_omp())
        for tile in image.tiles():
            tile.paint_boundary()
