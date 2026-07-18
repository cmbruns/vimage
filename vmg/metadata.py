from typing import Optional

import enum
import logging
from math import cos, radians, sin

import numpy
import PIL

from vmg.exif_orientation import ExifOrientation
from vmg.frame import DimensionsOmp

logger = logging.getLogger(__name__)


class InputFormat(enum.Enum):
    EQUIRECTANGULAR = 0   # stitched pano
    DUAL_FISHEYE = 1      # raw fisheye pair
    STANDARD_PHOTO = 2       # normal 2D photo


class PhotometricScale(enum.Enum):
    LINEAR = 0
    SRGB = 1


class ImageMetadata:
    """
    Sketch of class to contain image metadata.

    Responsibilities:
      * Store image metadata
      * Load image metadata
      * NOT signaling
    """

    def __init__(self):
        # Reasonable defaults wherever possible
        # General metadata
        self.file_name = None
        self.size_opx = DimensionsOmp(1, 1)  # logical size, exif oriented
        self.size_rpx = (1, 1)  # raw array size
        self.camera_model = None
        self.orientation: ExifOrientation = ExifOrientation.ROTATE_0
        self.rpx_R_opx = numpy.eye(2, dtype=numpy.float32)
        self.input_format = InputFormat.STANDARD_PHOTO
        self.photometric_scale = PhotometricScale.SRGB
        self.upper_bound = 255
        self.channel_count = 3
        self.data_max = 255  # Set data_max AFTER loading image bytes
        # Pano metadata
        self.initial_heading_degrees = 0.0
        self.initial_pitch_degrees = 0.0
        self.pcm_R_geo = numpy.eye(3, dtype=numpy.float32)
        # Dng metadata
        self.black_level = 0
        self.white_level = 255
        self.color_matrix1 = numpy.eye(3, dtype=numpy.float32)
        self.as_shot_neutral = (1.0, 1.0, 1.0)

    def load_tifffile_page(self, page):
        debug = True
        if debug:
            # print(page.dims)
            # print(page.eer_tags)
            # print(page.geotiff_tags)
            # print(page.get_resolution())
            # print(page.imagelength)
            # print(page.imagewidth)
            print(page.is_dng)
            print(repr(page.dtype))
            # print(page.is_tiled)  # TODO
            # print(page.photometric)  # 32803?
            # print(page.resolution)
            # print(page.size)
            for att in dir(page):
                if att.startswith("_"):
                    continue
                # print(att)
        # SIZE
        self.size_opx = DimensionsOmp(page.imagewidth, page.imagelength)
        # same, unless we find an exif orientation tag later
        self.size_rpx = tuple(int(x) for x in self.size_opx)
        # ORIENTATION (not tested yet)
        exif_ifd = page.tags.get("ExifTag")
        if exif_ifd:
            exif_tags = exif_ifd.value
            print(exif_tags)
            if 274 in exif_tags:
                orientation_index = exif_tags[274].value
                print(f"orientation {orientation_index}")
                # TODO
        self.upper_bound = numpy.iinfo(page.dtype).max
        self.channel_count = page.samplesperpixel
        # black level, white level
        for tag in page.tags.values():
            if tag.code == 50714:  # BlackLevel
                try:
                    self.black_level = tuple(b for b in tag.value)
                except TypeError:
                    assert tag.value % 1 == 0  # Whole number
                    self.black_level = tag.value
            elif tag.code == 50717:  # WhiteLevel
                assert tag.value % 1 == 0
                self.white_level = int(tag.value)
        print("BlackLevel:", self.black_level)
        print("WhiteLevel:", self.white_level)
        asn = page.tags['AsShotNeutral'].value
        assert len(asn) == 6
        self.as_shot_neutral = asn[0]/asn[1], asn[2]/asn[3], asn[4]/asn[5]
        cm = page.tags['ColorMatrix1'].value
        assert len(cm) == 18
        a = numpy.array(cm, numpy.float32).reshape(9, 2)
        self.color_matrix1 = (a[:, 0] / a[:, 1]).reshape(3, 3)
        print('ColorMatrix1', self.color_matrix1)
        # TODO full dng pipeline not done

    def load_pil_image(self, pil_image):
        w, h = pil_image.size
        self.size_rpx = w, h  # Unrotated dimension
        # TODO: move away from DimensionOmp and other frame vectors
        self.size_opx = DimensionsOmp(w, h)
        self.channel_count = channel_count_for_pil_mode.get(pil_image.mode, 3)
        exif0 = pil_image.getexif()
        exif = {
            PIL.ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in PIL.ExifTags.TAGS
        }
        for ifd_id in PIL.ExifTags.IFD:
            try:
                ifd = exif0.get_ifd(ifd_id)
                if ifd_id == PIL.ExifTags.IFD.GPSInfo:
                    resolve = PIL.ExifTags.GPSTAGS
                else:
                    resolve = PIL.ExifTags.TAGS
                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    exif[tag] = v
            except KeyError:
                pass
        try:
            xmp = pil_image.getxmp()  # noqa
        except AttributeError:
            xmp = {}
        for k in xmp:
            logger.debug(f"XMP {k} = '{xmp[k]}'")
        for k in exif:
            logger.debug(f"EXIF {k} = '{exif[k]}'")
        orientation_code: int = exif.get("Orientation", 1)
        self.orientation = ExifOrientation(orientation_code)
        logger.debug(f"Image EXIF orientation = {self.orientation}")
        self.rpx_R_opx = rotation_for_exif_orientation.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        self.size_opx = DimensionsOmp(*[abs(x) for x in (self.rpx_R_opx.T @ self.size_rpx)])
        w, h = self.size_opx
        model = exif.get("Model", "").lower()
        logger.debug(f"Camera model = '{model}'")
        if w != 2 * h:
            self.input_format = InputFormat.STANDARD_PHOTO  # Non-2:1 aspect is always a regular photo
        else:
            # 2016 Gear 360 unstitched image has certain sizes
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
                self.pcm_R_geo = m
            except (KeyError, TypeError):
                pass

    def load_exiftool(self, file_name):
        raise NotImplementedError


channel_count_for_pil_mode = {
    "1": 1,      # bilevel
    "L": 1,      # 8‑bit grayscale
    "P": 1,      # palette (indexed)
    "LA": 2,     # L + alpha
    "RGB": 3,
    "RGBA": 4,
    "CMYK": 4,
    "YCbCr": 3,
    "I": 1,      # 32‑bit signed integer
    "F": 1,      # 32‑bit float
}

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
