from math import asin, atan2, cos, degrees, pi, radians, sin
from typing import Optional

import numpy
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPoint, QSize, QObject
from PySide6.QtGui import Qt

from vmg.frame import DimensionsOmp, DimensionsQwn, LocationHpd, LocationObq, LocationNic, LocationOmp, LocationOnt, \
    LocationPrj, LocationQwn, LocationRelative
from vmg.image_data import ImageData
from vmg.pixel_filter import PixelFilter
from vmg.projection_360 import Projection360
from vmg.selection_box import SelectionBox, CursorHolder


class ViewState(QObject):
    """
    Q: Is there one ViewState per gl_widget? Or one per image?
    A: One per gl_widget. So the image could change during the lifetime of this ViewState.
    """

    def __init__(self, window_size: QSize, image_size=(1, 1)):
        super().__init__()
        self._size_qwn = DimensionsQwn(window_size.width(), window_size.height())
        self._size_omp = DimensionsOmp(* image_size)
        self.projection = Projection360.STEREOGRAPHIC
        self._zoom = 1.0  # windows per image
        self._is_360 = False
        self._center_rel = LocationRelative(0.5, 0.5)
        self._update_aspect_scale()
        self._raw_rot_omp = numpy.eye(2, dtype=numpy.float32)
        self.raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self.pixel_filter = PixelFilter.CATMULL_ROM
        self.sel_rect = SelectionBox()
        self.sel_rect.cursor_changed.connect(self.on_rect_cursor_changed)
        self._is_dragging = False
        self._previous_mouse_position = None
        self._background_color = [0.5, 0.5, 0.5, 0]

    @property
    def background_color(self):
        return self._background_color

    @background_color.setter
    def background_color(self, color):
        self._background_color[:3] = color[:3]

    @property
    def center_omp(self) -> LocationOmp:
        return LocationOmp(*self._center_rel * self._size_omp, 1)

    @property
    def center_rel(self) -> LocationRelative:
        return self._center_rel

    def _clamp_center(self):
        # TODO: we can still drag to the aspect padding...
        # Keep the center point on the actual image itself
        cx, cy = self._center_rel
        cx = max(0.0, cx)
        cy = max(0.0, cy)
        cx = min(1.0, cx)
        cy = min(1.0, cy)
        self._center_rel = LocationRelative(cx, cy)

    def context_menu_actions(self, qpoint: QPoint) -> list:
        result = []
        p_omp = self.omp_for_qpoint(qpoint)
        result.extend(self.sel_rect.context_menu_actions(p_omp, self.is_360))
        return result

    cursor_changed = QtCore.Signal(CursorHolder)

    @QtCore.Slot(CursorHolder)  # noqa
    def on_rect_cursor_changed(self, cursor_holder: CursorHolder):
        if cursor_holder.cursor is None:
            if self._is_dragging:
                self.cursor_changed.emit(CursorHolder(Qt.ClosedHandCursor))  # noqa
            else:
                self.cursor_changed.emit(CursorHolder(Qt.OpenHandCursor))  # noqa
        else:
            self.cursor_changed.emit(cursor_holder)  # noqa

    def drag_relative(self, prev: QPoint, curr: QPoint):
        prev_qwn = LocationQwn.from_qpoint(prev)
        curr_qwn = LocationQwn.from_qpoint(curr)
        if self.is_360:
            prev_hpd = self.hpd_for_qwn(prev_qwn)
            curr_hpd = self.hpd_for_qwn(curr_qwn)
            d_hpd = curr_hpd - prev_hpd
            # print(d_hpd)
            new_heading = self.view_heading_degrees + d_hpd.heading
            while new_heading <= -180:
                new_heading += 360
            while new_heading > 180:
                new_heading -= 360
            self.view_heading_degrees = new_heading
            new_pitch = self.view_pitch_degrees + d_hpd.pitch
            new_pitch = numpy.clip(new_pitch, -90, 90)
            self.view_pitch_degrees = new_pitch
            # print(f"New view direction heading={self.view_heading_degrees:.1f}° pitch={self.view_pitch_degrees:.1f}°")
        else:
            prev_omp = self.omp_for_qwn(prev_qwn)
            curr_omp = self.omp_for_qwn(curr_qwn)
            d_omp = curr_omp - prev_omp
            d_rel = (d_omp.x / self._size_omp.x, d_omp.y / self._size_omp.y)
            new_center = LocationRelative(self._center_rel.x + d_rel[0], self._center_rel.y + d_rel[1])
            self._center_rel[:] = new_center[:]
            self._clamp_center()
            # print(f"new way image center {self._center_rel}")

    @property
    def hover_min_omp(self):
        hover_min_qwn = 5  # How close do we need to be to start dragging?
        return self.omp_for_qwn(LocationQwn(hover_min_qwn, hover_min_qwn, 0)).x

    @staticmethod
    def hpd_for_ont(p_ont: LocationOnt) -> LocationHpd:
        return LocationHpd(
            degrees(atan2(p_ont.x, -p_ont.z)),
            degrees(asin(p_ont.y)),
        )

    def hpd_for_qwn(self, p_ont: LocationQwn) -> LocationHpd:
        return self.hpd_for_ont(self.ont_for_qwn(p_ont))

    @property
    def is_360(self) -> bool:
        """
        View state can override image 360-ness
        """
        return self._is_360

    def key_press_event(self, event: QtGui.QKeyEvent):
        if not self.is_360:
            self.sel_rect.key_press_event(event)

    def key_release_event(self, event: QtGui.QKeyEvent):
        if not self.is_360:
            self.sel_rect.key_release_event(event)

    def mouse_move_event(self, event) -> bool:
        # Rectangular selection is only valid in non-360 mode
        update_display = False
        event_consumed = False
        p_omp = self.omp_for_qpoint(event.pos())
        if not self.is_360:
            event_consumed, update_display = self.sel_rect.mouse_move_event(event, p_omp, self.hover_min_omp)
        if event_consumed:
            pass
        elif self._is_dragging:
            self.drag_relative(event.pos(), self._previous_mouse_position)
            self._previous_mouse_position = event.pos()
            update_display = True
        else:
            p_qwn = LocationQwn.from_qpoint(event.pos())
            if self.is_360:
                p_hpd = self.hpd_for_qwn(p_qwn)
                self.request_message.emit(  # noqa
                    f"heading = {p_hpd.heading:.1f}°  pitch = {p_hpd.pitch:.1f}°",
                    2000,
                )
            else:
                self.request_message.emit(  # noqa
                    f"image pixel = [{int(p_omp.x)}, {int(p_omp.y)}]",
                    2000,
                )
        return update_display

    def mouse_press_event(self, event):
        keep_cursor = self.sel_rect.mouse_press_event(
                event,
                self.omp_for_qpoint(event.pos()),
                self.hover_min_omp,
        )
        self._is_dragging = True
        self._previous_mouse_position = event.pos()
        if not keep_cursor:
            self.cursor_changed.emit(CursorHolder(Qt.ClosedHandCursor))  # noqa

    def mouse_release_event(self, event):
        self._is_dragging = False
        self._previous_mouse_position = None
        self.cursor_changed.emit(CursorHolder(Qt.OpenHandCursor))  # noqa
        p_omp = self.omp_for_qpoint(event.pos())
        self.sel_rect.mouse_release_event(event, p_omp)

    def ndc_xform_omp(self) -> numpy.ndarray:
        s1 = 2.0 * self.asc_qwn * self.zoom / self.asc_omp
        w_qwn, h_qwn = self._size_qwn
        return numpy.array([
            [s1 / w_qwn, 0, -s1 * self.center_omp.x / w_qwn],
            [0, -s1 / h_qwn, s1 * self.center_omp.y / h_qwn],
            [0, 0, 1],
        ], dtype=numpy.float32)

    def nic_for_qwn(self, p_qwn: LocationQwn) -> LocationNic:
        w_qwn, h_qwn = self._size_qwn
        zoom = self.zoom
        scale = 1.0 / self.asc_qwn / zoom
        nic_xform_qwn = numpy.array([
            [2*scale, 0, -w_qwn*scale],
            [0, -2*scale, h_qwn*scale],
            [0, 0, 1],
        ], dtype=numpy.float32)
        return LocationNic(*nic_xform_qwn @ p_qwn)

    def obq_for_prj(self, p_prj: LocationPrj) -> LocationObq:
        if self.projection == Projection360.GNOMONIC:
            d = 1.0 / (p_prj[0] ** 2 + p_prj[1] ** 2 + 1) ** 0.5
            p_obq = numpy.array([  # sphere orientation as viewed on screen
                d * p_prj[0],
                d * p_prj[1],
                -d,
            ], dtype=numpy.float32)
        elif self.projection == Projection360.EQUIDISTANT:
            r = (p_prj[0] ** 2 + p_prj[1] ** 2) ** 0.5
            d = sin(r) / r
            p_obq = numpy.array([  # sphere orientation as viewed on screen
                d * p_prj[0],
                d * p_prj[1],
                -cos(r),
            ], dtype=numpy.float32)
        elif self.projection == Projection360.EQUIRECTANGULAR:
            cy = cos(p_prj[1])
            p_obq = numpy.array([  # sphere orientation as viewed on screen
                sin(p_prj[0]) * cy,
                sin(p_prj[1]),
                -cos(p_prj[0]) * cy,
            ], dtype=numpy.float32)
        elif self.projection == Projection360.STEREOGRAPHIC:
            d = p_prj[0] ** 2 + p_prj[1] ** 2 + 4
            p_obq = numpy.array([  # sphere orientation as viewed on screen
                4 * p_prj[0] / d,
                4 * p_prj[1] / d,
                (d - 8) / d,
            ], dtype=numpy.float32)
        else:
            assert False  # What projection is this?
        return LocationObq(*p_obq)

    def omp_for_qpoint(self, qpoint: QPoint) -> LocationOmp:
        return self.omp_for_qwn(LocationQwn.from_qpoint(qpoint))

    def omp_for_qwn(self, p_qwn: LocationQwn) -> LocationOmp:
        p_nic = self.nic_for_qwn(p_qwn)
        center_omp = self.center_omp
        scale = self.asc_omp / 2
        omp_xform_nic = numpy.array([
            [scale, 0, center_omp.x],
            [0, -scale, center_omp.y],
            [0, 0, 1],
        ], dtype=numpy.float32)
        return LocationOmp(*omp_xform_nic @ p_nic)

    def omp_scale_qwn(self) -> float:
        return self._size_omp[1] / self._size_qwn[1] / self.zoom

    def omp_xform_ndc(self) -> numpy.ndarray:
        scale = self.asc_omp / 2.0 / self.asc_qwn / self.zoom
        w_qwn, h_qwn = self._size_qwn
        return numpy.array([
            [scale * w_qwn, 0, self.center_omp.x],
            [0, -scale * h_qwn, self.center_omp.y],
            [0, 0, 1],
        ], dtype=numpy.float32)

    def ont_for_obq(self, p_obq: LocationObq) -> LocationOnt:
        return LocationOnt(*self.ont_rot_obq @ p_obq)

    @property
    def ont_rot_obq(self) -> numpy.array:
        c = cos(radians(self.view_heading_degrees))
        s = sin(radians(self.view_heading_degrees))
        rot_heading = numpy.array([
            [c, 0, -s],
            [0, 1, 0],
            [s, 0, c],
        ], dtype=numpy.float32)
        c = cos(radians(self.view_pitch_degrees))
        s = sin(radians(self.view_pitch_degrees))
        rot_pitch = numpy.array([
            [1, 0, 0],
            [0, c, -s],
            [0, s, c],
        ], dtype=numpy.float32)
        return rot_heading @ rot_pitch

    def ont_for_qwn(self, p_qwn: LocationQwn) -> LocationOnt:
        p_prj = self.prj_for_qwn(p_qwn)
        p_obq = self.obq_for_prj(p_prj)
        return self.ont_for_obq(p_obq)

    def prj_for_qwn(self, p_qwn: LocationQwn) -> LocationPrj:
        p_nic = self.nic_for_qwn(p_qwn)
        prj_xform_nic = numpy.array([
            [pi/2, 0, 0],
            [0, pi/2, 0],
            [0, 0, 1],
        ], dtype=numpy.float32)
        return LocationPrj(*prj_xform_nic @ p_nic)

    @property
    def raw_rot_omp(self) -> numpy.array:
        return self._raw_rot_omp

    request_message = QtCore.Signal(str, int)

    def reset(self) -> None:
        self._zoom = 1.0  # windows per image
        self._center_rel = LocationRelative(0.5, 0.5)
        self.view_heading_degrees = 0.0
        self.view_pitch_degrees = 0.0

    def set_360(self, is_360: bool) -> None:
        self._is_360 = is_360
        self._update_aspect_scale()

    def set_image_data(self, image_data: ImageData):
        self._size_omp = image_data.size
        self._raw_rot_omp = image_data.raw_rot_omp
        self.raw_rot_ont = image_data.raw_rot_ont
        self._update_aspect_scale()

    def set_window_size(self, width, height):
        self._size_qwn = DimensionsQwn(width, height)
        self._update_aspect_scale()

    @QtCore.Slot()  # noqa
    def start_rect_with_no_point(self):
        self.sel_rect.begin(None)

    def _update_aspect_scale(self):
        w_omp, h_omp = self._size_omp
        w_qwn, h_qwn = self._size_qwn
        if self.is_360:
            if 1 > w_qwn/h_qwn:
                # window aspect is thin
                # So use width in scaling factor
                self.asc_omp = w_omp
                self.asc_qwn = w_qwn
            else:
                # Use height in scaling factor
                self.asc_omp = h_omp
                self.asc_qwn = h_qwn
        else:  # rectangular image
            if w_omp/h_omp > w_qwn/h_qwn:
                # Image aspect is wider than window aspect
                # So use width in scaling factor
                self.asc_omp = w_omp
                self.asc_qwn = w_qwn
            else:
                # Use height in scaling factor
                self.asc_omp = h_omp
                self.asc_qwn = h_qwn

    @property
    def view_heading_degrees(self):
        # interpret center point as heading/pitch in 360 mode
        return (self._center_rel.x - 0.5) * 360.0

    @view_heading_degrees.setter
    def view_heading_degrees(self, value):
        while value > 180.0:
            value -= 360.0
        while value <= -180.0:
            value += 360.0
        self._center_rel[0] = value / 360.0 + 0.5

    @property
    def view_pitch_degrees(self):
        # interpret center point as heading/pitch in 360 mode
        return (self._center_rel.y - 0.5) * 180.0

    @view_pitch_degrees.setter
    def view_pitch_degrees(self, value):
        value = numpy.clip(value, -90.0, 90.0)
        self._center_rel[1] = value / 180.0 + 0.5

    @property
    def window_size(self) -> DimensionsQwn:
        return self._size_qwn

    @property
    def zoom(self) -> float:
        return self._zoom

    def zoom_relative(self, zoom_factor: float, zoom_center: Optional[QPoint]):
        old_zoom = self._zoom
        new_zoom = self._zoom * zoom_factor
        # Limit zoom-out because you never need more than twice the image dimension to move around
        if new_zoom <= 0.30:
            new_zoom = 0.30
        self._zoom = new_zoom
        if zoom_center is not None:
            p_qwn = LocationQwn(zoom_center.x(), zoom_center.y(), 1)
            if self.is_360:
                self._zoom = old_zoom
                before_hpd = self.hpd_for_qwn(p_qwn)  # Before position
                self._zoom = new_zoom
                after_hpd = self.hpd_for_qwn(p_qwn)  # After position
                dh = after_hpd.heading - before_hpd.heading
                dp = after_hpd.pitch - before_hpd.pitch
                self.view_heading_degrees -= dh
                self.view_pitch_degrees -= dp
            else:
                self._zoom = old_zoom
                before_omp = self.omp_for_qwn(p_qwn)  # Before position
                self._zoom = new_zoom
                after_omp = self.omp_for_qwn(p_qwn)  # After position
                dx = after_omp.x - before_omp.x
                dy = after_omp.y - before_omp.y
                self._center_rel = self._center_rel - (dx/self._size_omp.x, dy/self._size_omp.y)
        if not self.is_360:
            self._clamp_center()
