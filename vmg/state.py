from math import asin, atan2, cos, degrees, pi, radians, sin
from typing import Optional

import numpy
import PIL.Image
from PIL import ExifTags
from PySide6.QtCore import QPoint, QSize, QObject, Slot

from vmg.coordinate import BasicVec2, BasicVec3
from vmg.pixel_filter import PixelFilter
from vmg.projection_360 import Projection360


class DimensionsOmp(BasicVec2):
    pass


class DimensionsQwn(BasicVec2):
    pass


class LocationHpd(BasicVec2):
    """
    Heading and pitch in degrees.
    Heading is measured in degrees clockwise from north.
    Pitch is measured as degrees above the horizon.
    """
    def __init__(self, heading: float, pitch: float)-> None:
        super().__init__(heading, pitch)

    def __repr__(self):
        return f"{self.__class__.__name__}(heading={self.x}, pitch={self.y})"

    def __str__(self):
        return f"(heading={self.x:.1f}°, pitch={self.y:.1f}°)"

    @property
    def heading(self):
        """Angle clockwise from north in degrees"""
        return self.x

    @property
    def pitch(self):
        """Angle above horizon in degrees"""
        return self.y


class LocationObq(BasicVec3):
    pass


class LocationNic(BasicVec3):
    pass


class LocationOmp(BasicVec3):
    pass


class LocationOnt(BasicVec3):
    pass


class LocationPrj(BasicVec3):
    pass


class LocationQwn(BasicVec3):
    @staticmethod
    def from_qpoint(qpoint: QPoint) -> "LocationQwn":
        return LocationQwn(qpoint.x(), qpoint.y(), 1)


class LocationRelative(BasicVec2):
    pass


class ImageState(object):
    def __init__(self, pil_image: PIL.Image.Image):
        raw_width, raw_height = pil_image.size  # Unrotated dimension
        self.size_raw = (raw_width, raw_height)
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        exif0 = pil_image.getexif()
        exif = {
            PIL.ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in PIL.ExifTags.TAGS
        }
        for ifd_id in ExifTags.IFD:
            try:
                ifd = exif0.get_ifd(ifd_id)
                if ifd_id == ExifTags.IFD.GPSInfo:
                    resolve = ExifTags.GPSTAGS
                else:
                    resolve = ExifTags.TAGS
                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    exif[tag] = v
            except KeyError:
                pass
        xmp = pil_image.getxmp()  # noqa
        orientation_code: int = exif.get("Orientation", 1)
        self._raw_rot_omp = self._exif_orientation_to_matrix.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        self.size_omp = DimensionsOmp(*[abs(x) for x in (self.raw_rot_omp.T @ self.size_raw)])
        if self.size_omp.x == 2 * self.size_omp.y:
            try:
                self._is_360 = True
                try:
                    # TODO: InitialViewHeadingDegrees
                    desc = xmp["xmpmeta"]["RDF"]["Description"]
                    heading = radians(float(desc["PoseHeadingDegrees"]))
                    pitch = radians(float(desc["PosePitchDegrees"]))
                    roll = radians(float(desc["PoseRollDegrees"]))
                    self._raw_rot_ont = numpy.array([
                        [cos(roll), -sin(roll), 0],
                        [sin(roll), cos(roll), 0],
                        [0, 0, 1],
                    ], dtype=numpy.float32)
                    self._raw_rot_ont = self._raw_rot_ont @ [
                        [1, 0, 0],
                        [0, cos(pitch), sin(pitch)],
                        [0, -sin(pitch), cos(pitch)],
                    ]
                    self._raw_rot_ont = self._raw_rot_ont @ [
                        [cos(heading), 0, sin(heading)],
                        [0, 1, 0],
                        [-sin(heading), 0, cos(heading)],
                    ]
                except (KeyError, TypeError):
                    pass
                if exif["Model"].lower().startswith("ricoh theta"):
                    # print("360")
                    pass  # TODO 360 image
            except KeyError:
                pass
        else:
            self._is_360 = False

    @property
    def is_360(self) -> bool:
        return self._is_360

    @property
    def raw_rot_omp(self) -> numpy.array:
        return self._raw_rot_omp

    @property
    def raw_rot_ont(self) -> numpy.array:
        return self._raw_rot_ont

    @property
    def size(self) -> DimensionsOmp:
        return self.size_omp

    _exif_orientation_to_matrix = {
        1: numpy.array([[1, 0], [0, 1]], dtype=numpy.float32),
        2: numpy.array([[-1, 0], [0, 1]], dtype=numpy.float32),
        3: numpy.array([[-1, 0], [0, -1]], dtype=numpy.float32),
        4: numpy.array([[1, 0], [0, -1]], dtype=numpy.float32),
        5: numpy.array([[0, 1], [1, 0]], dtype=numpy.float32),
        6: numpy.array([[0, 1], [-1, 0]], dtype=numpy.float32),
        7: numpy.array([[0, -1], [-1, 0]], dtype=numpy.float32),
        8: numpy.array([[0, -1], [1, 0]], dtype=numpy.float32),
    }


class ViewState(QObject):
    """
    Q: Is there one ViewState per gl_widget? Or one per image?
    A: One per gl_widget. So the image could change during the lifetime of this ViewState.
    """

    def __init__(self, window_size: QSize, image_size=(1, 1)):
        super().__init__()
        self._size_qwn = DimensionsQwn(window_size.width(), window_size.height())
        self._size_omp = DimensionsOmp(* image_size)
        self._projection = Projection360.STEREOGRAPHIC
        self._zoom = 1.0  # windows per image
        self._is_360 = False
        self._center_rel = LocationRelative(0.5, 0.5)
        self._view_heading_degrees = 0.0
        self._view_pitch_degrees = 0.0
        self._update_aspect_scale()
        self._raw_rot_omp = numpy.eye(2, dtype=numpy.float32)
        self.raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self.pixel_filter = PixelFilter.CATMULL_ROM

    @property
    def center_omp(self) -> LocationOmp:
        return LocationOmp(* self._center_rel * self._size_omp, 1)

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
        z = self.zoom
        if z <= 1:
            cx = 0.5
            cy = 0.5
        else:
            cx = min(cx, 1 - 0.5 / z)
            cx = max(cx, 0.5 / z)
            cy = min(cy, 1 - 0.5 / z)
            cy = max(cy, 0.5 / z)
        self._center_rel = LocationRelative(cx, cy)

    def drag_relative(self, prev: QPoint, curr: QPoint):
        prev_qwn = LocationQwn.from_qpoint(prev)
        curr_qwn = LocationQwn.from_qpoint(curr)
        if self.is_360:
            prev_hpd = self.hpd_for_qwn(prev_qwn)
            curr_hpd = self.hpd_for_qwn(curr_qwn)
            d_hpd = curr_hpd - prev_hpd
            print(d_hpd)
            new_heading = self._view_heading_degrees + d_hpd.heading
            while new_heading <= -180:
                new_heading += 360
            while new_heading > 180:
                new_heading -= 360
            self._view_heading_degrees = new_heading
            new_pitch = self._view_pitch_degrees + d_hpd.pitch
            new_pitch = numpy.clip(new_pitch, -90, 90)
            self._view_pitch_degrees = new_pitch
            print(f"New view direction heading={self._view_heading_degrees:.1f}° pitch={self._view_pitch_degrees:.1f}°")
        else:
            prev_omp = self.omp_for_qwn(prev_qwn)
            curr_omp = self.omp_for_qwn(curr_qwn)
            d_omp = curr_omp - prev_omp
            d_rel = (d_omp.x / self._size_omp.x, d_omp.y / self._size_omp.y)
            new_center = LocationRelative(self._center_rel.x + d_rel[0], self._center_rel.y + d_rel[1])
            self._center_rel[:] = new_center[:]
            self._clamp_center()
            # print(f"new way image center {self._center_rel}")

    @staticmethod
    def hpd_for_ont(p_ont: LocationOnt) -> LocationHpd:
        return LocationHpd(
            degrees(atan2(p_ont.x, -p_ont.z)),
            degrees(asin(p_ont.y)),
        )

    def hpd_for_qwn(self, p_ont: LocationOnt) -> LocationHpd:
        return self.hpd_for_ont(self.ont_for_qwn(p_ont))

    @property
    def is_360(self) -> bool:
        """
        View state can override image 360-ness
        """
        return self._is_360

    def nic_for_qwn(self, p_qwn: LocationQwn) -> LocationNic:
        w_qwn, h_qwn = self._size_qwn
        zoom = self.zoom
        scale = 1.0 / self.asc_qwn / zoom
        nic_xform_qwn = numpy.array([
            [2*scale, 0, -w_qwn*scale],
            [0, -2*scale, h_qwn*scale],
            [0, 0, 1],
        ], dtype=numpy.float32)
        return LocationNic(* nic_xform_qwn @ p_qwn)

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

    def omp_for_qwn(self, p_qwn: LocationQwn) -> LocationOmp:
        p_nic = self.nic_for_qwn(p_qwn)
        center_omp = self.center_omp
        scale = self.asc_omp / 2
        omp_xform_nic = numpy.array([
            [scale, 0, center_omp.x],
            [0, -scale, center_omp.y],
            [0, 0, 1],
        ], dtype=numpy.float32)
        return LocationOmp(* omp_xform_nic @ p_nic)

    def ont_for_obq(self, p_obq: LocationObq) -> LocationOnt:
        return LocationOnt(* self.ont_rot_obq @ p_obq)

    @property
    def ont_rot_obq(self) -> numpy.array:
        c = cos(radians(self._view_heading_degrees))
        s = sin(radians(self._view_heading_degrees))
        rot_heading = numpy.array([
            [c, 0, -s],
            [0, 1, 0],
            [s, 0, c],
        ], dtype=numpy.float32)
        c = cos(radians(self._view_pitch_degrees))
        s = sin(radians(self._view_pitch_degrees))
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
        return LocationPrj(* prj_xform_nic @ p_nic)

    @property
    def projection(self) -> Projection360:
        return self._projection

    @property
    def raw_rot_omp(self) -> numpy.array:
        return self._raw_rot_omp

    def reset(self) -> None:
        self._zoom = 1.0  # windows per image
        self._center_rel = LocationRelative(0.5, 0.5)
        self._view_heading_degrees = 0.0
        self._view_pitch_degrees = 0.0

    def set_360(self, is_360: bool) -> None:
        self._is_360 = is_360
        self._update_aspect_scale()

    def set_image_state(self, image_state: ImageState):
        self._size_omp = image_state.size
        self._raw_rot_omp = image_state.raw_rot_omp
        self.raw_rot_ont = image_state.raw_rot_ont
        self._update_aspect_scale()

    def set_window_size(self, width, height):
        self._size_qwn = DimensionsQwn(width, height)
        self._update_aspect_scale()

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
    def window_size(self) -> DimensionsQwn:
        return self._size_qwn

    @property
    def zoom(self) -> float:
        return self._zoom

    def zoom_relative(self, zoom_factor: float, zoom_center: Optional[QPoint]):
        old_zoom = self._zoom
        new_zoom = self._zoom * zoom_factor
        # Limit zoom-out because you never need more than twice the image dimension to move around
        if new_zoom <= 1:
            new_zoom = 1
        self._zoom = new_zoom
        if zoom_center is not None:
            # TODO 360 images...
            p_qwn = LocationQwn(zoom_center.x(), zoom_center.y(), 1)
            self._zoom = old_zoom
            before_omp = self.omp_for_qwn(p_qwn)  # Before position
            self._zoom = new_zoom
            after_omp = self.omp_for_qwn(p_qwn)  # After position
            dx = after_omp.x - before_omp.x
            dy = after_omp.y - before_omp.y
            self._center_rel = self._center_rel - (dx/self._size_omp.x, dy/self._size_omp.y)
        self._clamp_center()


class ProjectedPoint(object):
    """
    Immutable representation of a screen point at a moment in time
    """
    def __init__(self, qpoint: QPoint, view_state: ViewState):
        p_qwn = LocationQwn(qpoint.x(), qpoint.y(), 1.0)
        if view_state.is_360:
            self._heading_pitch = view_state.hpd_for_qwn(p_qwn)
            # print(self.heading_pitch)
        else:
            self._p_omp = LocationOmp(*view_state.omp_for_qwn(p_qwn))
            # print(self.omp)
            self._heading = 0
            self._pitch = 0

    @property
    def omp(self) -> LocationOmp:
        return self._p_omp

    @property
    def heading_pitch(self) -> LocationHpd:
        return self._heading_pitch
