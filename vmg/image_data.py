from enum import auto, Enum
import logging
from math import cos, radians, sin
from os import access, R_OK
from os.path import isfile

import numpy
from OpenGL import GL
from PIL import Image, ExifTags, UnidentifiedImageError
from PySide6 import QtCore
import tifffile
import turbojpeg
from tifffile import TiffFileError

from vmg.dng import DngImage
from vmg.frame import DimensionsOmp
from vmg.texture import Texture, ExifOrientation

logger = logging.getLogger(__name__)


class InputFormat(Enum):
    EQUIRECTANGULAR = 0   # stitched pano
    DUAL_FISHEYE = 1      # raw fisheye pair
    STANDARD_PHOTO = 2       # normal 2D photo


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
        self.orientation = ExifOrientation.UNSPECIFIED
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self._raw_rot_omp = numpy.eye(2, dtype=numpy.float32)
        self._input_format = InputFormat.STANDARD_PHOTO
        self.has_displayed = False
        self.array = None
        self.is_linear = False
        self.is_dng = False
        self.dng_image = None

    def file_is_readable(self) -> bool:
        file_name = self.file_name
        if not isfile(file_name):
            return False
        if not access(file_name, R_OK):
            return False
        return True

    @property
    def input_format(self) -> InputFormat:
        return self._input_format

    def load_jpeg_image(self) -> bool:
        try:
            jpeg = turbojpeg.TurboJPEG()  # TODO: maybe cache this
            with open(self.file_name, "rb") as in_file:
                jpeg_bytes = in_file.read()
            bgr_array = jpeg.decode(jpeg_bytes)
            self.texture = Texture.from_numpy(bgr_array, tex_format=GL.GL_BGR)
            self.array = bgr_array
            self.is_linear = False
            self.is_dng = False
            return True
        except ...:
            return False

    def open_pil_image(self) -> bool:
        try:
            self.pil_image = Image.open(self.file_name)
            self.is_linear = False  # Maybe more subtleties here...
            self.is_dng = False
            return True
        except UnidentifiedImageError as exc:
            logger.warning("Error loading image with PIL")
            return False

    def open_dng_image(self) -> bool:
        try:
            self.dng_image = DngImage(self.file_name)
            self.array = self.dng_image.bayer_array
            self.is_linear = True
            self.is_dng = True
            self.pil_image = Image.fromarray(self.array)
            return True
        except TiffFileError:
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
        for k in xmp:
            logger.debug(f"XMP {k} = '{xmp[k]}'")
        for k in exif:
            logger.debug(f"EXIF {k} = '{exif[k]}'")
        orientation_code: int = exif.get("Orientation", 1)
        self.orientation = ExifOrientation(orientation_code)
        logger.info(f"Image EXIF orientation = {self.orientation}")
        self._raw_rot_omp = self.rotation_for_exif_orientation.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        self.size_omp = DimensionsOmp(*[abs(x) for x in (self.raw_rot_omp.T @ self.size_raw)])
        w, h = self.size_omp.x, self.size_omp.y
        model = exif.get("Model", "").lower()
        logger.info(f"Camera model = '{model}'")
        if self.size_omp.x != 2 * self.size_omp.y:
            self._input_format = InputFormat.STANDARD_PHOTO  # Non-2:1 aspect is always a regular photo
        elif self.is_dng:
            self._input_format = InputFormat.DUAL_FISHEYE
        else:
            # 2016 Gear 360 raw image has certain sizes
            if model == "sm-c200" and ((w, h) == (7776, 3888) or (w, h) == (5792, 2896)):
                self._input_format = InputFormat.DUAL_FISHEYE
            elif model.startswith("ricoh theta"):
                self._input_format = InputFormat.EQUIRECTANGULAR
            else:
                self._input_format = InputFormat.EQUIRECTANGULAR  # Too inclusive...
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
