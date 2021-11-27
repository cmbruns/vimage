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
        image_list = app.arguments()[1:]
        if len(image_list) == 1:
            window.load_main_image(image_list[0])
        else:
            window.set_image_list(app.arguments()[1:], 0)
        window.show()
        sys.exit(app.exec())
