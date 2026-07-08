import logging
from math import radians

import numpy
from OpenGL import GL
from OpenGL.GL.EXT.texture_filter_anisotropic import GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT, GL_TEXTURE_MAX_ANISOTROPY_EXT
from OpenGL.GL.shaders import compileProgram, compileShader
import tifffile

from vmg.dng_texture import DngTextureAdapter
from vmg.render_state import RenderStateLike
from vmg.resources import resource_string
from vmg.shader import Sampler2DUniform, ViewerUniforms, PanoUniforms, FisheyeUniforms

logger = logging.getLogger(__name__)


class DngImage(object):
    # Loader thread resources:
    demosaic_framebuffer = None
    demosaic_program = None
    demosaic_vao = None

    # Render thread resources:
    # rect_program = None  # TODO: non-panorama dngs
    sphere_program = None
    uBayerTile = Sampler2DUniform("bayer_tile")
    uDemosaicTile = Sampler2DUniform("demosaic_tile")
    uViewer = ViewerUniforms()
    uPano = PanoUniforms()
    uFisheye = FisheyeUniforms()
    render_vao = None

    def __init__(self, file_name: str):
        with tifffile.TiffFile(file_name) as tif:
            page = tif.pages[0]
            self.bayer_array = page.asarray()
        assert self.bayer_array.dtype == numpy.uint16  # 16-bit
        assert len(self.bayer_array.shape) == 2  # formally monochrome
        self.bayer_texture_id = None
        self.demosaic_texture_id = None
        self.tile_X_img = numpy.eye(3, dtype=numpy.float32)  # TODO tiles
        self.load_sync = None
        self.texture = DngTextureAdapter(self)

    def initialize_gl(self):
        """Run this in the loader thread"""
        # First construct the lowest "lod -1" bayer image texture
        self.bayer_texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.bayer_texture_id)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
        bayer_h, bayer_w = self.bayer_array.shape
        # TODO: tiling
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,  # base mipmap
            GL.GL_R16,  # single channel
            bayer_w,
            bayer_h,
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
        demosaic_w = max(1, bayer_w // 2)
        demosaic_h = max(1, bayer_h // 2)
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

        # Clean up
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self.load_sync = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
        GL.glFlush()  # macOS probably
        logger.info("DNG demosaic complete")

    def paint_gl(self, state: RenderStateLike) -> bool:
        """Run this in the UI thread"""
        # start pregenerating some resources even if we are not ready to display
        if self.render_vao is None:
            self.render_vao = GL.glGenVertexArrays(1)
            self.sphere_program = compileProgram(
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
                uniform.get_location(self.sphere_program)
        assert self.render_vao is not None
        assert self.sphere_program is not None

        if self.load_sync is None:
            return False  # way too soon
        status = GL.glClientWaitSync(
            self.load_sync,
            GL.GL_SYNC_FLUSH_COMMANDS_BIT,
            0,
        )
        if status not in (GL.GL_ALREADY_SIGNALED, GL.GL_CONDITION_SATISFIED):
            return False  # too soon

        # TODO: maybe use rectangle image shader
        GL.glUseProgram(self.sphere_program)

        self.uDemosaicTile.set(1, self.demosaic_texture_id)
        self.uBayerTile.set(0, self.bayer_texture_id)
        self.uViewer.set(state=state, tile=self)
        self.uPano.set(state)
        self.uFisheye["df_fov_radians"].set(radians(195))  # TODO
        self.uFisheye["df_lens_rot_radians"].set(radians(0))  # TODO

        GL.glBindVertexArray(self.render_vao)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)  # Full screen quad

        return True
