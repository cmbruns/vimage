from PySide6 import QtCore, QtGui

from vmg._debug_session import agent_log


def _app_gui_thread():
    app = QtCore.QCoreApplication.instance()
    if app is None:
        return None
    return app.thread()


class OffscreenContext(QtCore.QObject):
    def __init__(self, parent, gl_context, gl_format):
        super().__init__(parent)
        self.parent_context = gl_context
        self.format = gl_format
        self.surface = None
        self.context = None

    def init_gl(self):
        """Create QOffscreenSurface and shared QOpenGLContext on the GUI thread."""
        if self.context is not None:
            return
        gui_thread = _app_gui_thread()
        current_thread = QtCore.QThread.currentThread()
        # #region agent log
        agent_log(
            "offscreen_context.py:init_gl",
            "creating offscreen surface and shared context",
            {
                "on_gui_thread": gui_thread is not None and current_thread is gui_thread,
            },
            hypothesis_id="H7",
        )
        # #endregion
        self.surface = QtGui.QOffscreenSurface()
        self.surface.setFormat(self.format)
        self.surface.create()
        assert self.surface.isValid()
        self.context = QtGui.QOpenGLContext()
        self.context.setShareContext(self.parent_context)
        self.context.setFormat(self.surface.requestedFormat())
        self.context.create()
        assert self.context.isValid()

    def __enter__(self):
        if self.context is None:
            raise RuntimeError(
                "OffscreenContext.init_gl() must be called on the GUI thread before loader use"
            )
        if not self.context.makeCurrent(self.surface):
            raise RuntimeError("Failed to make offscreen OpenGL context current")
        # #region agent log
        parent_valid = self.parent_context.isValid() if self.parent_context else False
        agent_log(
            "offscreen_context.py:__enter__",
            "offscreen context made current",
            {
                "parent_ctx_valid": parent_valid,
                "offscreen_ctx_valid": self.context.isValid(),
                "surface_valid": self.surface.isValid(),
                "context_thread_is_current": self.context.thread() is QtCore.QThread.currentThread(),
            },
            hypothesis_id="H7",
        )
        # #endregion
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.context.doneCurrent()
