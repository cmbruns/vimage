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


class AdjustType(enum.Enum):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    TOP = 3
    BOTTOM = 4


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
        self.adjusting = AdjustType.NONE

    cursorChanged = QtCore.Signal(QtGui.QCursor)

    def begin(self, p_omp: Optional[LocationOmp]):
        if p_omp is None:
            self.state = SelState.FINDING_FIRST_POINT
        else:
            self.first_point_omp = p_omp
            self.state = SelState.FINDING_SECOND_POINT
        self.cursorChanged.emit(Qt.CrossCursor)  # noqa

    @property
    def bottom(self) -> int:
        return self.left_top_right_bottom[3]

    @bottom.setter
    def bottom(self, value):
        self.left_top_right_bottom[3] = int(value + 0.5)

    @QtCore.Slot()
    def clear(self):
        self.state = SelState.INACTIVE
        self.left_top_right_bottom[:] = (0, 0, 0, 0)
        self.adjusting = AdjustType.NONE
        self.selection_shown.emit(False)

    def context_menu_actions(self, p_omp: LocationOmp) -> list:
        result = []
        start_action = StartRectAction()
        start_action.triggered.connect(lambda: self.begin(p_omp))  # noqa
        result.append(start_action)
        return result

    @property
    def first_point_omp(self):
        return self._first_point_omp

    @first_point_omp.setter
    def first_point_omp(self, xy):
        self._first_point_omp[:] = xy[:]
        self._update_shape()

    def _is_near_edge(self, p_omp, hover_min_omp) -> AdjustType:
        best = AdjustType.LEFT
        min_dist = abs(p_omp.x - self.left)
        if min_dist > abs(p_omp.x - self.right):
            min_dist = abs(p_omp.x - self.right)
            best = AdjustType.RIGHT
        if min_dist > abs(p_omp.y - self.top):
            min_dist = abs(p_omp.y - self.top)
            best = AdjustType.TOP
        if min_dist > abs(p_omp.y - self.bottom):
            min_dist = abs(p_omp.y - self.bottom)
            best = AdjustType.BOTTOM
        if min_dist > hover_min_omp:
            return AdjustType.NONE
        return best

    @property
    def left(self) -> int:
        return self.left_top_right_bottom[0]

    @left.setter
    def left(self, value):
        self.left_top_right_bottom[0] = int(value + 0.5)

    def mouse_move_event(self, _event, p_omp, hover_min_omp) -> tuple[bool, bool]:
        update_display = False
        event_consumed = False
        if self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            update_display = True
            event_consumed = True
        elif self.state == SelState.COMPLETE:
            if self.adjusting == AdjustType.NONE:
                # Show correct cursor when hovering
                adj = self._is_near_edge(p_omp, hover_min_omp)
                if adj == AdjustType.LEFT:
                    self.cursorChanged.emit(Qt.SizeHorCursor)
                elif adj == AdjustType.RIGHT:
                    self.cursorChanged.emit(Qt.SizeHorCursor)
                elif adj == AdjustType.TOP:
                    self.cursorChanged.emit(Qt.SizeVerCursor)
                elif adj == AdjustType.BOTTOM:
                    self.cursorChanged.emit(Qt.SizeVerCursor)
                else:
                    self.cursorChanged.emit(None)
            else:
                if self.adjusting == AdjustType.LEFT:
                    self.left = p_omp.x
                elif self.adjusting == AdjustType.RIGHT:
                    self.right = p_omp.x
                elif self.adjusting == AdjustType.TOP:
                    self.top = p_omp.y
                elif self.adjusting == AdjustType.BOTTOM:
                    self.bottom = p_omp.y
                update_display = True
                event_consumed = True
        return event_consumed, update_display

    def mouse_press_event(self, _event: QtGui.QMouseEvent, p_omp, hover_min_omp) -> bool:
        keep_cursor = False
        if self.state == SelState.FINDING_FIRST_POINT:
            self.first_point_omp = p_omp
            self.second_point_omp = p_omp
            self.state = SelState.FINDING_SECOND_POINT
            keep_cursor = True
        elif self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            self.state = SelState.COMPLETE
            self.cursorChanged.emit(None)  # noqa
            self.selection_shown.emit(True)
            keep_cursor = True
        elif self.state == SelState.COMPLETE:
            self.adjusting = self._is_near_edge(p_omp, hover_min_omp)
            if self.adjusting != AdjustType.NONE:
                keep_cursor = True
        return keep_cursor

    def mouse_release_event(self, _event, p_omp):
        if self.adjusting != AdjustType.NONE:
            self.adjusting = AdjustType.NONE
        elif self.state == SelState.FINDING_SECOND_POINT:
            self.second_point_omp = p_omp
            self.state = SelState.COMPLETE
            self.cursorChanged.emit(None)  # noqa
            self.selection_shown.emit(True)

    @property
    def right(self) -> int:
        return self.left_top_right_bottom[2]

    @right.setter
    def right(self, value):
        self.left_top_right_bottom[2] = int(value + 0.5)

    @QtCore.Slot()  # noqa
    def start_rect_with_no_point(self):
        self.begin(None)

    @property
    def second_point_omp(self):
        return self._second_point_omp

    @second_point_omp.setter
    def second_point_omp(self, xy):
        self._second_point_omp[:] = xy[:]
        self._update_shape()

    selection_shown = QtCore.Signal(bool)

    @property
    def top(self) -> int:
        return self.left_top_right_bottom[1]

    @top.setter
    def top(self, value):
        self.left_top_right_bottom[1] = int(value + 0.5)

    def _update_shape(self):
        # Keep the values sorted
        self.left = min(
            self._first_point_omp[0],
            self._second_point_omp[0],
        )
        self.top = min(
            self._first_point_omp[1],
            self._second_point_omp[1],
        )
        self.right = max(
            self._first_point_omp[0],
            self._second_point_omp[0],
        )
        self.bottom = max(
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
