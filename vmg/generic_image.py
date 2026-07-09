import logging
from math import cos, radians, sin

import numpy
from PIL import Image, ExifTags, UnidentifiedImageError
from vmg.frame import DimensionsOmp
from vmg.input_format import InputFormat
from vmg.texture import ExifOrientation

logger = logging.getLogger(__name__)


class PillowImage:
    def __init__(self):
        self.input_format = InputFormat.STANDARD_PHOTO
        self.file_name = None
        self.pil_image = None
        self.size_raw = [0, 0]
        self.size_omp = DimensionsOmp(0, 0)
        self.raw_rot_ont = numpy.eye(3, dtype=numpy.float32)  # pano orientation
        self.raw_rot_omp = numpy.eye(2, dtype=numpy.float32)  # exif orientation

    def load_from_file(self, file_name: str) -> bool:
        try:
            self.pil_image = Image.open(self.file_name)
            self.file_name = file_name
            self.read_pil_metadata()
            return True
        except UnidentifiedImageError as exc:
            logger.warning("Error loading image with PIL")
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
        for k in xmp:
            logger.debug(f"XMP {k} = '{xmp[k]}'")
        for k in exif:
            logger.debug(f"EXIF {k} = '{exif[k]}'")
        orientation_code: int = exif.get("Orientation", 1)
        orientation = ExifOrientation(orientation_code)
        logger.info(f"Image EXIF orientation = {orientation}")
        self.raw_rot_omp = self.rotation_for_exif_orientation.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        self.size_omp = DimensionsOmp(*[abs(x) for x in (self.raw_rot_omp.T @ self.size_raw)])
        w, h = self.size_omp.x, self.size_omp.y
        model = exif.get("Model", "").lower()
        logger.info(f"Camera model = '{model}'")
        if self.size_omp.x != 2 * self.size_omp.y:
            self.input_format = InputFormat.STANDARD_PHOTO  # Non-2:1 aspect is always a regular photo
        else:
            # 2016 Gear 360 raw image has certain sizes
            if model == "sm-c200" and ((w, h) == (7776, 3888) or (w, h) == (5792, 2896)):
                self.input_format = InputFormat.DUAL_FISHEYE
            elif model.startswith("ricoh theta"):
                self.input_format = InputFormat.EQUIRECTANGULAR
            else:
                self.input_format = InputFormat.EQUIRECTANGULAR  # Too inclusive...
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
                self.raw_rot_ont = m
            except (KeyError, TypeError):
                pass

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
