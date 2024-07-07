import logging
from math import cos, radians, sin
from os import access, R_OK
from os.path import isfile

import numpy
from OpenGL import GL
from PIL import Image, ExifTags, UnidentifiedImageError
from PySide6 import QtCore
import turbojpeg

from vmg.frame import DimensionsOmp
from vmg.texture import Texture

logger = logging.getLogger(__name__)


class ImageData(QtCore.QObject):
    def __init__(self, file_name: str, parent=None):
        super().__init__(parent=parent)
        self.file_name = str(file_name)
        self.pil_image = None
        self.texture = None
        self.exif = {}
        self.xmp = {}
        self.size_raw = [0, 0]
        self.size_omp = DimensionsOmp(0, 0)
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self._raw_rot_omp = numpy.eye(2, dtype=numpy.float32)
        self._is_360 = False
        self.has_displayed = False

    def file_is_readable(self) -> bool:
        file_name = self.file_name
        if not isfile(file_name):
            return False
        if not access(file_name, R_OK):
            return False
        return True

    @property
    def is_360(self) -> bool:
        return self._is_360

    def load_jpeg_image(self) -> bool:
        # TODO: split into smaller parts
        try:
            jpeg = turbojpeg.TurboJPEG()  # TODO: maybe cache this
            with open(self.file_name, "rb") as in_file:
                jpeg_bytes = in_file.read()
            bgr_array = jpeg.decode(jpeg_bytes)
            self.texture = Texture.from_numpy(bgr_array, tex_format=GL.GL_BGR)
            return True
        except ...:
            return False

    def open_pil_image(self) -> bool:
        try:
            self.pil_image = Image.open(self.file_name)
            return True
        except UnidentifiedImageError as exc:
            logger.exception("Error loading image with PIL")
            return False

    def read_pil_metadata(self):
        raw_width, raw_height = self.pil_image.size  # Unrotated dimension
        self.size_raw = (raw_width, raw_height)
        exif0 = self.pil_image.getexif()
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in ExifTags.TAGS
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
        try:
            xmp = self.pil_image.getxmp()  # noqa
        except AttributeError:
            xmp = {}
        self.xmp = xmp
        self.exif = exif
        orientation_code: int = exif.get("Orientation", 1)
        self._raw_rot_omp = self.rotation_for_exif_orientation.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
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
                    m = numpy.array([
                        [cos(roll), -sin(roll), 0],
                        [sin(roll), cos(roll), 0],
                        [0, 0, 1],
                    ], dtype=numpy.float32)
                    m = m @ [
                        [1, 0, 0],
                        [0, cos(pitch), sin(pitch)],
                        [0, -sin(pitch), cos(pitch)],
                    ]
                    m = m @ [
                        [cos(heading), 0, sin(heading)],
                        [0, 1, 0],
                        [-sin(heading), 0, cos(heading)],
                    ]
                    self._raw_rot_ont = m
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
    def raw_rot_omp(self) -> numpy.array:
        return self._raw_rot_omp

    @property
    def raw_rot_ont(self) -> numpy.array:
        return self._raw_rot_ont

    @property
    def size(self) -> DimensionsOmp:
        return self.size_omp

    rotation_for_exif_orientation = {
        1: numpy.array([[1, 0], [0, 1]], dtype=numpy.float32),
        2: numpy.array([[-1, 0], [0, 1]], dtype=numpy.float32),
        3: numpy.array([[-1, 0], [0, -1]], dtype=numpy.float32),
        4: numpy.array([[1, 0], [0, -1]], dtype=numpy.float32),
        5: numpy.array([[0, 1], [1, 0]], dtype=numpy.float32),
        6: numpy.array([[0, 1], [-1, 0]], dtype=numpy.float32),
        7: numpy.array([[0, -1], [-1, 0]], dtype=numpy.float32),
        8: numpy.array([[0, -1], [1, 0]], dtype=numpy.float32),
    }
