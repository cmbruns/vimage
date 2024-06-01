"""
Classes and methods for semantically distinguishing coordinate systems.
"""


from numbers import Number

import numpy
from PySide6 import QtCore


class BasicVec(object):
    """Base class for vector coordinates"""
    def __init__(self, *args) -> None:
        self._v = numpy.array(args, dtype=numpy.float32)

    def __getitem__(self, item):
        return self._v[item]

    def __len__(self):
        return len(self._v)


class BasicVec2(BasicVec):
    """Base class for semantic 2D coordinate types"""
    def __init__(self, x: Number, y: Number) -> None:
        super().__init__(x, y)

    @property
    def x(self):
        return self._v[0]

    @property
    def y(self):
        return self._v[1]


class BasicVec3(BasicVec):
    """Base class for semantic 3D coordinate types"""
    def __init__(self, x: Number, y: Number, z: Number) -> None:
        super().__init__(x, y, z)

    @property
    def x(self):
        return self._v[0]

    @property
    def y(self):
        return self._v[1]

    @property
    def z(self):
        return self._v[2]


class NdcPos(BasicVec2):
    """
    Location within a window.
    Units: half window extents
    Origin: lower left near (OpenGL convention)
    """

    def __repr__(self):
        return f"NdcPos(x={self.x:.4f}, y={self.y:.4f})"

    @staticmethod
    def from_window(win: "WindowPos", width: float, height: float) -> "NdcPos":
        w, h = width, height
        # TODO: cache this matrix somewhere when the window size changes
        ndc_xform_win = numpy.array([
            [2.0 / w, 0, -1],
            [0, -2.0 / h, 1],
            [0, 0, 1],
        ], dtype=numpy.float32)
        ndc = ndc_xform_win @ (win.x, win.y, 1)  # Homogeneous coordinates
        return NdcPos(ndc[0], ndc[1])


class WindowPos(BasicVec2):
    """
    Location within a window.
    Units: display screen pixels
    Origin: upper left (Qt convention)
    """
    def __repr__(self):
        return f"WindowPos(x={self.x:.1f}, y={self.y:.1f})"

    @staticmethod
    def from_qpoint(qpoint: QtCore.QPoint) -> "WindowPos":
        return WindowPos(qpoint.x(), qpoint.y())
