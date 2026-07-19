import traceback

import abc
import logging
from PIL import Image
from math import radians
from typing import Callable, OrderedDict

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT

from vmg.interfaces import RenderStateLike, ImageLike
from vmg.metadata import PhotometricScale, InputFormat
from vmg.resources import resource_stream, resource_string
from vmg.shader_exception import compile_shader
from vmg.texture import Tile, LoadProgress

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


class NumeralShader(IImageShader):
    """Paints numeric intensity values onto very zoomed in pixels"""
    def __init__(self):
        self.program = None
        self.numeral_texture_id = None
        self.uNdc_X_omp = Uniform("ndc_X_omp", GL.glUniformMatrix3fv)
        self.uTile = Sampler2DUniform("tile")
        self.uNumerals = Sampler2DUniform("numerals")
        self.uChannelCount = Uniform("channel_count", GL.glUniform1i)
        self.uFormatMax = Uniform("format_max", GL.glUniform1f)
        self.uDataMax = Uniform("data_max", GL.glUniform1f)
        self.uRotation = Uniform("rotation", GL.glUniformMatrix2fv)
        self.uPixelNumerals = Uniform("pixel_numerals", GL.glUniform1i)
        with resource_stream("vmg.images", "hex_digits_df.png") as df:
            numeral_pil = Image.open(df)
            self.numeral_array = numpy.array(numeral_pil)

    def initialize_gl(self) -> None:
        # Texturize numeral signed distance field
        self.numeral_texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.numeral_texture_id)
        assert len(self.numeral_array.shape) == 2  # monochrome
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_G, GL.GL_RED)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_SWIZZLE_B, GL.GL_RED)
        h, w = self.numeral_array.shape
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RED,
            w, h,
            0,
            GL.GL_RED,
            GL.GL_UNSIGNED_BYTE,
            self.numeral_array,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)

        self.program = compileProgram(
            compile_shader("vmg.glsl",
                           ["tile_rect.vert"], GL.GL_VERTEX_SHADER),
            compile_shader("vmg.glsl",
                           [
                               "shared.frag",
                               "numeral.frag",
                           ], GL.GL_FRAGMENT_SHADER),
        )
        for u in (
            self.uNdc_X_omp,
            self.uTile,
            self.uNumerals,
            self.uChannelCount,
            self.uFormatMax,
            self.uDataMax,
            self.uRotation,
            self.uPixelNumerals,
        ):
            u.get_location(self.program)

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        if self.program is None:
            self.initialize_gl()
        GL.glUseProgram(self.program)
        self.uNdc_X_omp.set(1, True, state.ndc_xform_omp())
        self.uNumerals.set(1, self.numeral_texture_id)
        self.uChannelCount.set(image.md.channel_count)
        self.uFormatMax.set(image.md.upper_bound)
        self.uDataMax.set(image.md.data_max)
        self.uRotation.set(1, False, image.md.rpx_R_opx)
        self.uPixelNumerals.set(state.pixel_numerals.value)
        for tile in image.tiles():
            self.uTile.set(0, tile.texture_id)
            assert tile.vao is not None
            # TODO: this is for standard photos only
            GL.glBindVertexArray(tile.vao)
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)


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
        self.numeral_shader = NumeralShader()

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
            self.numeral_shader.initialize_gl()
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
        self.input_is_linear.set(image.photometric_scale == PhotometricScale.LINEAR)
        image.paint_gl(self, state)
        self.numeral_shader.paint_gl(state, image)
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
        self.numeral_shader = NumeralShader()

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
            self.numeral_shader.initialize_gl()
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
        self.numeral_shader.paint_gl(state, image)
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
        self.uRenderPass = Uniform("render_pass", GL.glUniform1i)
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
        for u in self.brightness, self.input_is_linear, self.uRenderPass:
            u.get_location(self.shader)

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
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
        self.uRenderPass.set(1)
        image.paint_gl(self, state)
        if image.input_format == InputFormat.DUAL_FISHEYE:
            # second render pass for rear lens
            self.uRenderPass.set(2)
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
        try:
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
        except BaseException as exc:
            logger.error(exc)
            raise

    def paint_gl(self, state: RenderStateLike, image: ImageLike) -> None:
        if self.shader is None:
            self.initialize_gl()
        GL.glUseProgram(self.shader)
        self.uPano["window_zoom"].set(state.zoom)
        self.uViewer["pixelFilter"].set(state.pixel_filter.value)
        self.uPano["ont_rot_obq"].set(1, True, state.ont_rot_obq)
        self.uPano["raw_rot_ont"].set(1, True, image.raw_rot_ont)
        self.uPano["window_size"].set(*[int(x) for x in state.window_size])
        self.uPano["display_projection"].set(state.display_projection.value)
        self.uFisheye["df_fov_radians"].set(self.df_fov_radians)
        self.uFisheye["df_lens_rot_radians"].set(self.df_lens_rot_radians)
        self.uViewer["brightness"].set(state.brightness)
        # self.input_is_linear.set(image.photometric_scale == PhotometricScale.LINEAR) # NOT USED?
        is_complete = True
        for tile in image.tiles():
            # GL.glUniformMatrix3fv(program.tile_X_img_location, 1, True, tile.tile_X_img)
            self.uViewer["tile_X_img"].set(1, True, tile.tile_X_img)
            # GL.glUniform4f(program.uv_bounds_location, *tile.uv_bounds)  # TODO: Not used in pano mode?
            self.uDemosaicTile.set(1, tile.demosaic_texture_id)
            self.uBayerTile.set(0, tile.bayer_texture_id)
            if not tile.paint_gl():
                is_complete = False
            if is_complete and image.load_progress != LoadProgress.DISPLAYED:
                image.load_progress = LoadProgress.DISPLAYED
                image.sq.image_displayed.emit(image)  # noqa  # TODO: maybe don't hoist this here...
            # break  # just one tile for testing
        # image.paint_gl(self.tile_X_img_location, self.uv_bounds_location)
        # Clean up
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0) # unbind from active unit
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

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
