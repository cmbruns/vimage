import pkg_resources
import platform
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtCore import QEvent, Qt

from vmg.main_window import VimageMainWindow


class VimageApplication(QtWidgets.QApplication):
    def event(self, event):
        if event.type() == QEvent.FileOpen:
            file_name = event.file()
            if file_name.endswith("Contents/plugins/python-ce/helpers/pydev/pydevd.py"):
                pass  # Elide strange signal when debugging in pycharm on Mac
            else:
                self.on_file_open_event.emit(event.file())
        return super().event(event)

    on_file_open_event = QtCore.Signal(str)


class VimageApp(object):
    def __init__(self):
        f = QSurfaceFormat()
        f.setProfile(QSurfaceFormat.CoreProfile)
        f.setVersion(4, 1)
        QSurfaceFormat.setDefaultFormat(f)
        # Respect dark mode setting on windows
        if platform.system == "Windows":
            sys.argv += ['-platform', 'windows:darkmode=2']
        app = VimageApplication(sys.argv)
        app.setStyle("fusion")  # Maybe looks better than default Vista style?
        app.setAttribute(Qt.AA_EnableHighDpiScaling)  # No effect on custom cursor size
        app.setOrganizationName("rotatingpenguin.com")
        app.setApplicationName("vimage")
        app.setApplicationDisplayName("vimage")
        with VimageMainWindow() as window:
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
            app.on_file_open_event.connect(window.file_open_event)
            sys.exit(app.exec())
