import enum
import pkg_resources
from typing import Optional

import numpy
from PySide6 import QtCore, QtGui
from PySide6.QtGui import Qt

from vmg.frame import LocationOmp


class SelState(enum.Enum):
    INACTIVE = 0
    FINDING_FIRST_POINT = 1
    FINDING_SECOND_POINT = 2
    COMPLETE = 3


class RectangularSelection(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.left_top_right_bottom = numpy.array(
            [0, 0, 0, 0],
            dtype=numpy.uint32,
        )
        self._first_point_omp = [0, 0]
        self._second_point_omp = [0, 0]
        self.state = SelState.INACTIVE
        self._next_start_omp: Optional[LocationOmp] = None

    cursorChanged = QtCore.Signal(QtGui.QCursor)

    def begin(self, p_omp: Optional[LocationOmp]):
        if p_omp is None:
            self.state = SelState.FINDING_FIRST_POINT
        else:
            self.first_point_omp = p_omp
            self.state = SelState.FINDING_SECOND_POINT
        self.cursorChanged.emit(Qt.CrossCursor)  # noqa

    def context_menu_actions(self, p_omp: LocationOmp) -> list:
        result = []
        start_action = StartRectAction()
        self._next_start_omp = p_omp
        start_action.triggered.connect(self.start_rect_with_cached_point)  # noqa
        result.append(start_action)
        return result

    @property
    def first_point_omp(self):
        return self._first_point_omp

    @first_point_omp.setter
    def first_point_omp(self, xy):
        self._first_point_omp[:] = xy[:]
        self._update_shape()

    @QtCore.Slot()  # noqa
    def start_rect_with_cached_point(self):
        self.begin(self._next_start_omp)

    @QtCore.Slot()  # noqa
    def start_rect_with_no_point(self):
        self.begin(None)

    def mouse_move_event(self, _event, p_omp) -> bool:
        if self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            return True
        else:
            return False

    def mouse_press_event(self, _event, p_omp) -> bool:
        if self.state == SelState.FINDING_FIRST_POINT:
            self.first_point_omp = p_omp
            self.second_point_omp = p_omp
            self.state = SelState.FINDING_SECOND_POINT
            return True
        elif self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            self.state = SelState.COMPLETE
            self.cursorChanged.emit(None)  # noqa
            return True
        else:
            return False

    def mouse_release_event(self, _event, p_omp) -> bool:
        if self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            self.state = SelState.COMPLETE
            self.cursorChanged.emit(None)  # noqa
            return False  # no update needed
        else:
            return False

    @property
    def second_point_omp(self):
        return self._second_point_omp

    @second_point_omp.setter
    def second_point_omp(self, xy):
        self._second_point_omp[:] = xy[:]
        self._update_shape()

    def _update_shape(self):
        # Keep the values sorted
        self.left_top_right_bottom[0] = min(
            self._first_point_omp[0],
            self._second_point_omp[0],
        )
        self.left_top_right_bottom[1] = min(
            self._first_point_omp[1],
            self._second_point_omp[1],
        )
        self.left_top_right_bottom[2] = max(
            self._first_point_omp[0],
            self._second_point_omp[0],
        )
        self.left_top_right_bottom[3] = max(
            self._first_point_omp[1],
            self._second_point_omp[1],
        )


_rect_icon = None


class StartRectAction(QtGui.QAction):
    def __init__(self):
        global _rect_icon
        if _rect_icon is None:
            _rect_icon = QtGui.QIcon(pkg_resources.resource_filename("vmg.images", "box_icon.png"))
        super().__init__(
            text="Start selecting a rectangle here",
            icon=_rect_icon,
        )
