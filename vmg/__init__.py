import sys

from PySide6 import QtWidgets

from vmg.main_window import VimageMainWindow


class VimageApp(object):
    def __init__(self):
        app = QtWidgets.QApplication(sys.argv)
        app.setOrganizationName("rotatingpenguin.com")
        app.setApplicationName("vimage")
        app.setApplicationDisplayName("vimage")
        window = VimageMainWindow()
        args = app.arguments()
        if len(args) > 1:
            window.load_image(args[1])
        window.show()
        sys.exit(app.exec())
