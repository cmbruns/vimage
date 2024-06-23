"""
Compare speed of different ways of handling images

  * pre-multiply alpha
    * using numpy
    * using PIL
    * using OpenGL
    * not pre-multiplying

  * srgb to linear
    * not doing that
    * numpy
    * ?

  * pre-rotate orientation
    * not
    * PIL
    * OpenGL

  * load large jpeg
    * PIL
    * (intermediate) PIL thumbnail/draft
    * PIL-SIMD
    * Turbo-JPEG
"""
import numpy
import pkg_resources
from OpenGL import GL

from PIL.Image import Resampling
from PySide6.QtGui import QSurfaceFormat, QOpenGLContext, QOffscreenSurface
from PySide6.QtWidgets import QApplication
import turbojpeg
from turbojpeg import TJFLAG_FASTUPSAMPLE, TJFLAG_FASTDCT

from vmg.image_data import ImageData
from vmg.performance import Performance


jpeg = turbojpeg.TurboJPEG()


def main():
    hopper_name = pkg_resources.resource_filename("vmg.images", "hopper.gif")
    for file_name in [
        # hopper_name,
        # r"\\diskstation\Public\Pictures\2024\WaterLeak\R0016689.JPG",
        # r"C:\Users\cmbruns\Pictures\Space_Needle_panorama_large.jpg",
        r"C:\Users\cmbruns\Pictures\_Bundles_for_Berlin__More_production!.jpg",  # 30kx42k
        # r"C:\Users\cmbruns\Pictures\borf3.jpg",
    ]:
        # profile_image(file_name)
        turbo_jpeg_case(file_name)


def profile_image(file_name):
    print(f"Loading file {file_name} :")
    with Performance(message="check existence", indent=1):
        image_data = ImageData(str(file_name))
        _file_exists = image_data.file_is_readable()
    with Performance(message="open PIL image", indent=1):
        image_data.open_pil_image()
    with Performance(message="read PIL metadata", indent=1):
        image_data.read_pil_metadata()
    with Performance(message="load PIL image", indent=1):
        # image_data.pil_image.thumbnail([200, 200], resample=Resampling.NEAREST)
        bytes1 = image_data.pil_image.tobytes()
    with Performance(message="convert to numpy", indent=1):
        numpy_image = numpy.array(image_data.pil_image)


def turbo_jpeg_case(file_name):
    with Performance(message="copy jpeg file to memory", indent=1):
        with open(file_name, "rb") as in_file:
            jpeg_bytes = in_file.read()
    with Performance(message="load with turbojpeg SCALE (1, 4)", indent=1):
        bgr_array = jpeg.decode(jpeg_bytes, scaling_factor=(1, 4))
    with Performance(message="load with turbojpeg scale (1, 2)", indent=1):
        bgr_array = jpeg.decode(jpeg_bytes, scaling_factor=(1, 2))
    with Performance(message="load with turbojpeg FAST", indent=1):
        bgr_array = jpeg.decode(jpeg_bytes, flags=TJFLAG_FASTUPSAMPLE | TJFLAG_FASTDCT)
    with Performance(message="load with turbojpeg", indent=1):
        bgr_array = jpeg.decode(jpeg_bytes)


def opengl_something():
    if not QApplication.instance():
        _app = QApplication()  # somehow necessary...
    gl_format = QSurfaceFormat()
    gl_format.setMajorVersion(4)
    gl_format.setMinorVersion(1)  # MacOS limited to 4.1
    gl_context = QOpenGLContext()
    gl_context.setFormat(gl_format)
    gl_context.create()
    assert gl_context.isValid()
    surface = QOffscreenSurface()
    surface.setFormat(gl_format)
    surface.create()
    assert surface.isValid()
    gl_context.makeCurrent(surface)
    fbo = GL.glGenFramebuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    color_texture = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, color_texture)
    GL.glTexImage2D(
        GL.GL_TEXTURE_2D,
        0,
        GL.GL_RGB,
        800, 600,
        0,
        GL.GL_RGB,
        GL.GL_UNSIGNED_BYTE,
        None,
    )
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
    GL.glBindTexture(GL.GL_TEXTURE_2D, 0);
    GL.glFramebufferTexture2D(
        GL.GL_FRAMEBUFFER,
        GL.GL_COLOR_ATTACHMENT0,
        GL.GL_TEXTURE_2D,
        color_texture,
        0
    )
    assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == GL.GL_FRAMEBUFFER_COMPLETE
    # GL.glClearColor(1, 1, 1, 1)
    # GL.glClear(GL.GL_COLOR_BUFFER_BIT)
    #
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
    GL.glDeleteFramebuffers(1, [fbo, ])
    gl_context.doneCurrent()


if __name__ == "__main__":
    main()
    # opengl_something()
