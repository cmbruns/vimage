import pkg_resources

from PySide6.QtGui import QSurfaceFormat, QOpenGLContext, QOffscreenSurface
from PySide6.QtWidgets import QApplication

from vmg.image_loader import Performance, ImageData


def main():
    file_name = pkg_resources.resource_filename("vmg.images", "hopper.gif")
    profile_image(file_name)


def profile_image(file_name):
    print(f"Loading file {file_name} :")
    with Performance(message="check existence", indent=1):
        image_data = ImageData(str(file_name))
        file_exists = image_data.file_is_readable()
    with Performance(message="open PIL image", indent=1):
        image_data.open_pil_image()


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
    gl_context.doneCurrent()


if __name__ == "__main__":
    main()
    opengl_something()
