import abc
import numpy


class IFrame(abc.ABC):
    pass


class ITransform(abc.ABC):
    pass


class IVec(abc.ABC):
    pass


window_frame = IFrame()


class WindowVec(IVec):
    def __init__(self, x, y):
        self.vec = numpy.array([x, y], dtype=numpy.uint16)

    @property
    def frame(self):
        return window_frame
