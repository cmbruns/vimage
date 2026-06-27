import logging
import pkg_resources
import platform
import sys

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QIcon, QSurfaceFormat

from .main_window import VimageMainWindow
from .except_hook import ExceptHook
from .log import StdIoRedirector
from ._debug_session import agent_log


logger = logging.getLogger(__name__)


class VimageApplication(QtWidgets.QApplication):
    def event(self, event):
        if event.type() == QEvent.FileOpen:
            file_name = event.file()
            if file_name.endswith("Contents/plugins/python-ce/helpers/pydev/pydevd.py"):
                pass  # Elide strange signal when debugging in pycharm on Mac
            else:
                self.on_file_open_event.emit(event.file())  # noqa
        return super().event(event)

    on_file_open_event = QtCore.Signal(str)


class VimageApp(object):
    def __init__(self):
        # import vmg.except_hook
        # Top level logger must be created before this point (see vmg.__init__.py)
        # with StdIoRedirector():
        with ExceptHook():
            logger.info("Launching vimage app")
            app = self.init_app()
            self.run_main_window(app)

    @staticmethod
    def run_main_window(app):
        with VimageMainWindow() as window:
            image_list = app.arguments()[1:]
            # #region agent log
            agent_log(
                "app.py:run_main_window",
                "startup argv image list",
                {"image_count": len(image_list), "first_image": image_list[0] if image_list else None},
                hypothesis_id="H4",
            )
            # #endregion
            if len(image_list) == 1:
                window.load_main_image(image_list[0])
            else:
                window.set_image_list(app.arguments()[1:], 0)
            # #region agent log
            agent_log(
                "app.py:run_main_window",
                "calling window.show()",
                {"gl_initialized": window.imageWidgetGL.isValid()},
                hypothesis_id="H1",
            )
            # #endregion
            window.show()
            # #region agent log
            agent_log(
                "app.py:run_main_window",
                "window.show() returned",
                {
                    "gl_initialized": window.imageWidgetGL.isValid(),
                    "widget_size": [window.imageWidgetGL.width(), window.imageWidgetGL.height()],
                },
                hypothesis_id="H4",
            )
            # #endregion
            icon_file = pkg_resources.resource_filename("vmg", "images/vimage2.ico")
            icon = QIcon(icon_file)
            app.setWindowIcon(icon)
            window.setWindowIcon(icon)
            app.on_file_open_event.connect(window.file_open_event)
            sys.exit(app.exec())

    @staticmethod
    def init_app():
        QtWidgets.QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        f = QSurfaceFormat()
        f.setProfile(QSurfaceFormat.CoreProfile)
        f.setVersion(4, 1)
        QSurfaceFormat.setDefaultFormat(f)
        # Respect dark mode setting on windows
        if platform.system() == "Windows":
            sys.argv += ['-platform', 'windows:darkmode=2']
        app = VimageApplication(sys.argv)
        app.setStyle("fusion")  # Maybe looks better than default Vista style?
        app.setAttribute(Qt.AA_EnableHighDpiScaling)  # No effect on custom cursor size
        app.setOrganizationName("rotatingpenguin.com")
        app.setApplicationName("vimage")
        app.setApplicationDisplayName("vimage")
        return app


__all__ = [
    "VimageApp"
]
