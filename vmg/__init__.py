import pkg_resources
import sys

from PySide6 import QtWidgets
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtCore import Qt

from vmg.main_window import VimageMainWindow


class VimageApp(object):
    def __init__(self):
        f = QSurfaceFormat()
        f.setProfile(QSurfaceFormat.CoreProfile)
        f.setVersion(4, 1)
        QSurfaceFormat.setDefaultFormat(f)
        app = QtWidgets.QApplication(sys.argv)
        app.setAttribute(Qt.AA_EnableHighDpiScaling)  # No effect on custom cursor size
        app.setOrganizationName("rotatingpenguin.com")
        app.setApplicationName("vimage")
        app.setApplicationDisplayName("vimage")
        window = VimageMainWindow()
        image_list = app.arguments()[1:]
        if len(image_list) == 1:
            window.load_main_image(image_list[0])
        else:
            window.set_image_list(app.arguments()[1:], 0)
        window.show()
        icon_file = pkg_resources.resource_filename("vmg", "images/vimage2.ico")
        icon = QIcon(icon_file)
        app.setWindowIcon(icon)
        window.setWindowIcon(icon)
        sys.exit(app.exec())
