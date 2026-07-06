"""
Proof of concept creation of an opengl texture containing a demosaiced
version of a Bayer RGGB digital negative DNG image file.
"""

from inspect import cleandoc

import numpy
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
from PySide6.QtGui import (
    QGuiApplication,
    QOffscreenSurface,
    QOpenGLContext,
    QSurfaceFormat,
)
import tifffile

file_name = "C:/Users/cmbruns/Pictures/360CameraSamples/XiaomiMisphere/IMG_20260705_133914.DNG"
with tifffile.TiffFile(file_name) as tif:
    page = tif.pages[0]
    array = page.asarray()
h, w = array.shape
print(w, h, array.dtype)

# Must create an application before creating a surface
app = QGuiApplication([])
surface = QOffscreenSurface()
fmt = QSurfaceFormat()
fmt.setRenderableType(QSurfaceFormat.OpenGL)
fmt.setProfile(QSurfaceFormat.CoreProfile)
fmt.setVersion(4, 1)          # macOS maximum
fmt.setDepthBufferSize(0)     # not needed for offscreen compute
fmt.setStencilBufferSize(0)   # not needed
fmt.setRedBufferSize(8)
fmt.setGreenBufferSize(8)
fmt.setBlueBufferSize(8)
fmt.setAlphaBufferSize(8)
fmt.setSwapBehavior(QSurfaceFormat.SingleBuffer)
fmt.setOption(QSurfaceFormat.DebugContext)  # optional but recommended
surface.setFormat(fmt)
# Must create a context before creating a surface
context = QOpenGLContext()
context.setFormat(surface.requestedFormat())
context.create()
assert context.isValid()
surface.create()
assert surface.isValid()

context.makeCurrent(surface)

bayer_texture_id = GL.glGenTextures(1)
GL.glBindTexture(GL.GL_TEXTURE_2D, bayer_texture_id)
GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # In case width is odd
GL.glTexImage2D(
    GL.GL_TEXTURE_2D,
    0,  # base mipmap
    GL.GL_R16UI,  # single channel
    w,
    h,
    0,  # border
    GL.GL_RED,
    GL.GL_UNSIGNED_SHORT,  # 16 bit
    array,
)
# We always want literally exact texel values, and no mipmapping
GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
# Make all fetches outside the texture return transparent black
GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)
GL.glTexParameterfv(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_BORDER_COLOR, [0, 0, 0, 0])
# Sanity check bayer texture
print(GL.glGetTexLevelParameteriv(GL.GL_TEXTURE_2D, 0, GL.GL_TEXTURE_WIDTH))
print(GL.glGetTexLevelParameteriv(GL.GL_TEXTURE_2D, 0, GL.GL_TEXTURE_HEIGHT))

# Bayer texture size (level 0)
bayer_w = w
bayer_h = h
# Theoretical mipmap level 1 size
demosaic_w = max(1, bayer_w // 2)
demosaic_h = max(1, bayer_h // 2)
# Create framebuffer
fbo = GL.glGenFramebuffers(1)
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
# Create demosaic color texture
demosaic_tex = GL.glGenTextures(1)
GL.glBindTexture(GL.GL_TEXTURE_2D, demosaic_tex)
# Allocate storage for level 0 of demosaic tile (RGB float)
GL.glTexImage2D(
    GL.GL_TEXTURE_2D,
    0,              # mip level
    GL.GL_RGBA8,       # internal format (linear float)
    demosaic_w,
    demosaic_h,
    0,             # border
    GL.GL_RGBA,           # upload format
    GL.GL_UNSIGNED_BYTE,          # upload type
    None            # no initial data
)
# Attach texture to framebuffer
GL.glFramebufferTexture2D(
    GL.GL_FRAMEBUFFER,
    GL.GL_COLOR_ATTACHMENT0,
    GL.GL_TEXTURE_2D,
    demosaic_tex,
    0  # mip level
)

# Set draw buffers
GL.glDrawBuffers(1, [GL.GL_COLOR_ATTACHMENT0])

# Check completeness
status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
if status != GL.GL_FRAMEBUFFER_COMPLETE:
    raise RuntimeError(f"Framebuffer incomplete: 0x{status:X}")

program = compileProgram(
    compileShader(cleandoc("""
        #version 410
        
        // host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
        const vec4 SCREEN_QUAD[4] = vec4[4](
            vec4( 1, -1, 0.5, 1),  // lower right
            vec4( 1,  1, 0.5, 1),  // upper right
            vec4(-1, -1, 0.5, 1),  // lower left
            vec4(-1,  1, 0.5, 1)   // upper left
        );
        
        const vec2 TEX_COORD[4] = vec2[4](
            vec2( 1,  1),  // lower right
            vec2( 1,  0),  // upper right
            vec2( 0,  1),  // lower left
            vec2( 0,  0)   // upper left
        );
        
        out vec2 tex_coord;
        
        void main() {
            gl_Position = SCREEN_QUAD[gl_VertexID];
            tex_coord = TEX_COORD[gl_VertexID];
        }
    """), GL.GL_VERTEX_SHADER),
    compileShader(cleandoc("""
        #version 410
    
        uniform sampler2D bayer;
        in vec2 tex_coord;
        out vec4 color;
    
        void main() {
            // color = vec4(0, 1, 0, 1);  // pure green for testing
            // crude copy of bayer for testing
            color = texture(bayer, tex_coord);
            color = vec4(5 * color.rrr, color.a);
        }
    """), GL.GL_FRAGMENT_SHADER),
)
vao = GL.glGenVertexArrays(1)
GL.glBindVertexArray(vao)
GL.glViewport(0, 0, demosaic_w, demosaic_h)

# Render
GL.glClearColor(1, 0.9, 0.9, 1)  # pink color for testing
GL.glClear(GL.GL_COLOR_BUFFER_BIT)
GL.glBindTexture(GL.GL_TEXTURE_2D, bayer_texture_id)
GL.glUseProgram(program)
GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
# TODO run the demosaic shader

pixels = GL.glReadPixels(
    0, 0, demosaic_w, demosaic_h,
    GL.GL_RGBA,
    GL.GL_UNSIGNED_BYTE
)
# Convert to a NumPy array
img = numpy.frombuffer(pixels, dtype=numpy.uint8)
img = img.reshape((demosaic_h, demosaic_w, 4))
# Flip vertically (OpenGL origin is bottom-left)
img = numpy.flip(img, axis=0)
# Convert to PIL image
image = Image.fromarray(img, mode="RGBA")
# Save PNG
image.save("demosaic_test_output.png")
print("Wrote demosaic_test_output.png")

# Clean up
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
context.doneCurrent()
