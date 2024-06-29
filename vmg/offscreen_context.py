from PySide6 import QtCore, QtGui


class OffscreenContext(QtCore.QObject):
    def __init__(self, parent, gl_context, gl_format):
        super().__init__(parent)
        self.parent_context = gl_context
        self.format = gl_format
        self.surface = None
        self.context = None

    def init_gl(self):
        if self.context is not None:
            return
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
        self.init_gl()
        self.context.makeCurrent(self.surface)

    def __exit__(self, _type, _value, _traceback):
        self.context.doneCurrent()
