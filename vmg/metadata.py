import json

import enum
import logging
from math import cos, radians, sin, degrees
from typing import Optional

import exiftool
import numpy
from numpy.typing import NDArray
import PIL
from PIL import ExifTags

from vmg.dng_color import LightSource
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
        self.black_level = (0, 0, 0)
        self.white_level = 255
        self.color_matrix1 = numpy.eye(3, dtype=numpy.float32)
        self.color_matrix2 = numpy.eye(3, dtype=numpy.float32)
        self.as_shot_neutral = (1.0, 1.0, 1.0)
        self.illuminant1 = LightSource.STANDARD_LIGHT_A
        self.illuminant2 = LightSource.D65

    def load_tifffile_page(self, page):
        debug = True
        if debug:
            # print(page.dims)
            # print(page.eer_tags)
            # print(page.geotiff_tags)
            # print(page.get_resolution())
            # print(page.imagelength)
            # print(page.imagewidth)
            # print(page.is_dng)
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
        # EXIF ORIENTATION (not tested yet)
        exif_ifd = page.tags.get("ExifTag")
        if exif_ifd:
            exif_tags = exif_ifd.value
            # print(exif_tags)
            if 274 in exif_tags:
                orientation_index = exif_tags[274].value
                print(f"orientation {orientation_index}")
                # TODO
        w, h = self.size_opx
        # TODO: pano orientation
        xmp_tag = page.tags.get("XMP")
        print("XMP tag", xmp_tag)
        # Input format  TODO: subtler decision tree
        if w == 2 * h:
            self.input_format = InputFormat.DUAL_FISHEYE
        else:
            self.input_format = InputFormat.STANDARD_PHOTO
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
        # TODO full dng pipeline not done

    def load_pil_image(self, pil_image):
        w, h = pil_image.size
        self.size_rpx = w, h  # Unrotated dimension
        # TODO: move away from DimensionsOmp and other frame vectors
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
                # Normalize to a list
                if isinstance(desc, dict):
                    desc_list = [desc]
                else:
                    desc_list = desc
                is_pano: Optional[bool] = None  # don't know yet
                pose_heading = 0.0
                pose_pitch = 0.0
                pose_roll = 0.0
                initial_heading = 0.0
                initial_pitch = 0.0
                initial_roll = 0.0
                for d in desc_list:
                    if "PoseHeadingDegrees" in d:
                        pose_heading = radians(float(d["PoseHeadingDegrees"]))
                        is_pano = True
                    if "PosePitchDegrees" in d:
                        pose_pitch = radians(float(d["PosePitchDegrees"]))
                        is_pano = True
                    if "PoseRollDegrees" in d:
                        pose_roll = radians(float(d["PoseRollDegrees"]))
                        is_pano = True
                    if "InitialViewHeadingDegrees" in d:
                        self.initial_heading_degrees = float(d["InitialViewHeadingDegrees"])
                        is_pano = True
                    if "InitialViewPitchDegrees" in d:
                        self.initial_pitch_degrees = float(d["InitialViewPitchDegrees"])
                        is_pano = True
                    if "InitialViewRollDegrees" in d:
                        self.initial_roll_degrees = float(d["InitialViewRollDegrees"])
                        is_pano = True
                Use360PanoReferenceConvention = False
                if Use360PanoReferenceConvention:
                    pose_roll = -pose_roll
                if pose_heading != 0 or pose_pitch != 0 or pose_roll != 0:
                    logger.info(
                        f"Pose heading, pitch, roll = ({degrees(pose_heading)}, {degrees(pose_pitch)}, {degrees(pose_roll)})")
                # TODO: use new frame shorthands everywhere
                # https://github.com/cmbruns/vimage/issues/74
                # Photographer's camera pose
                pcm_rot_geo = numpy.array([
                    [cos(pose_roll), -sin(pose_roll), 0],
                    [sin(pose_roll), cos(pose_roll), 0],
                    [0, 0, 1],
                ], dtype=numpy.float32)
                pcm_rot_geo = pcm_rot_geo @ [
                    [1, 0, 0],
                    [0, cos(pose_pitch), sin(pose_pitch)],
                    [0, -sin(pose_pitch), cos(pose_pitch)],
                ]
                pcm_rot_geo = pcm_rot_geo @ [
                    [cos(pose_heading), 0, sin(pose_heading)],
                    [0, 1, 0],
                    [-sin(pose_heading), 0, cos(pose_heading)],
                ]
                # Initial View
                # TODO incorporate IVW into pipeline separate from GEO
                self.pcm_R_geo = pcm_rot_geo
            except (KeyError, TypeError):
                pass

    def load_exiftool(self, file_name):
        with exiftool.ExifTool() as et:
            raw = et.execute("-j", file_name)
            exif = json.loads(raw)[0]
        debug = True
        if debug:
            print(json.dumps(exif, indent=2, sort_keys=True))
        w, h = exif["EXIF:ImageWidth"], exif["EXIF:ImageHeight"]
        self.size_rpx = w, h
        self.size_opx = DimensionsOmp(w, h)
        self.channel_count = exif["EXIF:SamplesPerPixel"]
        orientation_code = exif["EXIF:Orientation"]
        self.orientation = ExifOrientation(orientation_code)
        self.rpx_R_opx = rotation_for_exif_orientation.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        self.size_opx = DimensionsOmp(*[abs(x) for x in (self.rpx_R_opx.T @ self.size_rpx)])
        if "EXIF:CFAPattern2" in exif:
            assert exif["EXIF:CFAPattern2"] == "0 1 1 2"  # We only know RGGB
        if "EXIF:BlackLevel" in exif:
            black = [float(x)/self.upper_bound for x in exif["EXIF:BlackLevel"].split()]
            if len(black) == 4:
                # average the two green channels
                black = black[0], 0.5 * (black[1] + black[2]), black[3]
            assert len(black) == 3
            self.black_level = black
            print(self.black_level)
        if "EXIF:WhiteLevel" in exif:
            self.white_level = float(exif["EXIF:WhiteLevel"]) / self.upper_bound
        if "EXIF:AsShotNeutral" in exif:
            self.as_shot_neutral = [float(x) for x in exif["EXIF:AsShotNeutral"].split()]
            assert len(self.as_shot_neutral) == 3
        if "EXIF:ColorMatrix1" in exif:
            cm1 = exif["EXIF:ColorMatrix1"].split()
            assert len(cm1) == 9
            self.color_matrix1 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))
        if "EXIF:ColorMatrix2" in exif:
            cm1 = exif["EXIF:ColorMatrix2"].split()
            assert len(cm1) == 9
            self.color_matrix2 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))

        w, h = self.size_opx
        if w != 2 * h:
            self.input_format = InputFormat.STANDARD_PHOTO  # Non-2:1 aspect is always a regular photo
        else:  # Panorama
            if "EXIF:DNGVersion" in exif:
                self.input_format = InputFormat.DUAL_FISHEYE
            else:
                self.input_format = InputFormat.EQUIRECTANGULAR
            pose_heading = 0.0
            pose_pitch = 0.0
            pose_roll = 0.0


def calculate_dng_t(
        as_shot_neutral,
        color_matrix1: NDArray,
        color_matrix2: NDArray,
        illuminant1: LightSource = LightSource.STANDARD_LIGHT_A,
        illuminant2: LightSource = LightSource.D65,
):
    """
    Calculates the DNG matrix interpolation weight 't' from AsShotNeutral.

    Parameters:
      as_shot_neutral: list or numpy.array of 3 floats, e.g., [0.52, 1.0, 0.63]
      color_matrix1:   3x3 numpy.array representing ColorMatrix1 (Tungsten)
      color_matrix2:   3x3 numpy.array representing ColorMatrix2 (Daylight)
      illuminant1:     DNG tag integer for CalibrationIlluminant1 (Default: 17 = Standard Illuminant A)
      illuminant2:     DNG tag integer for CalibrationIlluminant2 (Default: 21 = D65)
    """

    # 1. Map standard DNG Illuminant tags to their exact nominal Kelvin temperatures
    # Reference: DNG Spec Chapter 6 (CalibrationIlluminant tags)
    illuminant_temps = {
        1: 2856,  # Standard Illuminant A (Tungsten)
        17: 2856,  # Standard Illuminant A
        18: 4874,  # Standard Illuminant B
        19: 6774,  # Standard Illuminant C
        20: 5003,  # D50
        21: 6504,  # D65
        22: 7504,  # D75
        23: 5455,  # D55
    }

    temp1 = illuminant_temps.get(illuminant1, 2856)
    temp2 = illuminant_temps.get(illuminant2, 6504)

    # 2. Derive a generic, un-white-balanced Camera-to-XYZ matrix
    # DNG spec defines ColorMatrix as XYZ -> Camera. We use its inverse.
    # We use a base blend of CM1 and CM2 just to calculate a valid local proxy spatial environment.
    cm_base = (color_matrix1 + color_matrix2) / 2.0
    cam_to_xyz = numpy.linalg.inv(cm_base)

    # 3. Project the AsShotNeutral raw channel scaling into CIE XYZ space
    # (AsShotNeutral is inverted to represent white balance multipliers)
    wb_gains = 1.0 / numpy.array(as_shot_neutral)
    xyz = numpy.dot(cam_to_xyz, wb_gains)

    # 4. Convert XYZ to CIE xy chromaticity coordinates
    xyz_sum = xyz[0] + xyz[1] + xyz[2]
    if xyz_sum == 0:
        return 0.5  # Fail-safe midpoint if data evaluates to zero
    x = xyz[0] / xyz_sum
    y = xyz[1] / xyz_sum

    # 5. McCamy's Cubic Approximation to find Correlated Color Temperature (CCT)
    # Convert xy to CIE 1960 uv landscape vectors
    u = (4.0 * x) / (-2.0 * x + 12.0 * y + 3.0)
    v = (6.0 * y) / (-2.0 * x + 12.0 * y + 3.0)

    # Epicenter of the chromatic adaptation path
    n = (u - 0.3320) / (v - 0.1858)
    cct_as_shot = -449.0 * (n ** 3) + 3525.0 * (n ** 2) - 6823.3 * n + 5524.07

    # Bound the evaluated temperature logically
    cct_as_shot = numpy.clip(cct_as_shot, 2000, 12000)

    # 6. Calculate 't' using inverse temperatures (Mired scale) per DNG rules
    mired_as_shot = 1.0 / cct_as_shot
    mired_1 = 1.0 / temp1
    mired_2 = 1.0 / temp2

    # Guard against division by zero if both illuminants are identical
    if mired_1 == mired_2:
        return 0.0

    t = (mired_as_shot - mired_1) / (mired_2 - mired_1)

    # Clamp t tightly between [0.0, 1.0] per Adobe specification framework
    return float(numpy.clip(t, 0.0, 1.0))


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
