import json

import enum
import logging
from math import cos, radians, sin, degrees
from numpy import linalg
from typing import Optional

import exiftool
import numpy
import PIL
from PIL import ExifTags

from vmg.dng_color import LightSource, calculate_dng_t
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
        self.initial_roll_degrees = 0.0
        self.pcm_R_geo = numpy.eye(3, dtype=numpy.float32)
        # Dng metadata
        self.black_level = (0.0, 0.0, 0.0)
        self.white_level = (1.0, 1.0, 1.0)
        self.as_shot_neutral = (1.0, 1.0, 1.0)
        self.color_matrix1 = numpy.eye(3, dtype=numpy.float32)
        self.color_matrix2 = numpy.eye(3, dtype=numpy.float32)
        # Convert camera sensor reference values to linear sRGB
        self.lsr_X_wba = numpy.eye(3, dtype=numpy.float32)
        self.baseline_exposure = 0.0

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
            # print(repr(page.dtype))
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
                # print(f"orientation {orientation_index}")
                # TODO
        w, h = self.size_opx
        # TODO: pano orientation
        xmp_tag = page.tags.get("XMP")
        # print("XMP tag", xmp_tag)
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
        # print("BlackLevel:", self.black_level)
        # print("WhiteLevel:", self.white_level)
        asn = page.tags['AsShotNeutral'].value
        assert len(asn) == 6
        as_shot_neutral = asn[0]/asn[1], asn[2]/asn[3], asn[4]/asn[5]
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
        debug = False
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
            try:
                black = [float(x)/self.upper_bound for x in exif["EXIF:BlackLevel"].split()]
            except AttributeError:
                black = [float(exif["EXIF:BlackLevel"])/self.upper_bound] * 3
            if len(black) == 4:
                # average the two green channels
                black = black[0], 0.5 * (black[1] + black[2]), black[3]
            assert len(black) == 3
            self.black_level = black
        if "EXIF:WhiteLevel" in exif:
            try:
                white = [float(x)/self.upper_bound for x in exif["EXIF:WhiteLevel"].split()]
            except AttributeError:
                white = [float(exif["EXIF:WhiteLevel"])/self.upper_bound] * 3
            self.white_level = white
        if "EXIF:AsShotNeutral" in exif:
            self.as_shot_neutral = [float(x) for x in exif["EXIF:AsShotNeutral"].split()]
            assert len(self.as_shot_neutral) == 3
            print(self.as_shot_neutral)
        if "EXIF:ColorMatrix1" in exif:
            cm1 = exif["EXIF:ColorMatrix1"].split()
            assert len(cm1) == 9
            self.color_matrix1 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))
        if "EXIF:ColorMatrix2" in exif:
            cm1 = exif["EXIF:ColorMatrix2"].split()
            assert len(cm1) == 9
            self.color_matrix2 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))
        if "EXIF:CalibrationIlluminant1" in exif:
            calibration_illuminant1 = LightSource(int(exif["EXIF:CalibrationIlluminant1"]))
        if "EXIF:CalibrationIlluminant2" in exif:
            calibration_illuminant2 = LightSource(int(exif["EXIF:CalibrationIlluminant2"]))
        if "EXIF:BaselineExposure" in exif:
            self.baseline_exposure = float(exif["EXIF:BaselineExposure"])
        # TODO: some dng might have a ForwardMatrix available...
        # Interpolate color matrix
        dng_t = calculate_dng_t(
            self.as_shot_neutral,
            self.color_matrix1, self.color_matrix2,
            calibration_illuminant1, calibration_illuminant2,
        )
        rfv_X_d50 = self.color_matrix1 * (1 - dng_t) + self.color_matrix2 * dng_t
        # ColorMatrix requires us to undo white balance first, then invert the matrix.
        # wb_gain_matrix = numpy.diag([1/x for x in self.as_shot_neutral])
        # xyz_X_sensor = linalg.inv(color_matrix) @ wb_gain_matrix
        lsr_X_d65 = numpy.array([
            [+3.2404542, -1.5371385, -0.4985314],
            [-0.9692660,  1.8760108,  0.0415560],
            [+0.0556434, -0.2040259,  1.0572252],
        ])
        d65_X_d50 = numpy.array([  # Bradford
            [+0.9555766, -0.0230393,  0.0631636],
            [-0.0283858,  1.0099416,  0.0210077],
            [+0.0123140, -0.0205076,  1.3299115]
        ])
        d50_X_rfv = linalg.inv(rfv_X_d50)
        rfv_X_wba = numpy.diag(self.as_shot_neutral)
        self.lsr_X_wba = lsr_X_d65 @ d65_X_d50 @ d50_X_rfv @ rfv_X_wba

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
            if "EXIF:PoseHeadingDegrees" in exif:
                pose_heading = radians(float(exif["EXIF:PoseHeadingDegrees"]))
            elif "EXIF:GPSImgDirection" in exif:
                pose_heading = radians(float(exif["EXIF:GPSImgDirection"]))
            if "EXIF:PosePitchDegrees" in exif:
                pose_pitch = radians(float(exif["EXIF:PosePitchDegrees"]))
            elif "Composite:RicohPitch" in exif:
                pose_pitch = radians(float(exif["Composite:RicohPitch"]))
            if "EXIF:PoseRollDegrees" in exif:
                pose_roll = radians(float(exif["EXIF:PoseRollDegrees"]))
            elif "Composite:RicohRoll" in exif:
                pose_roll = radians(float(exif["Composite:RicohRoll"]))
            if "EXIF:InitialViewHeadingDegrees" in exif:
                self.initial_heading_degrees = float(exif["EXIF:InitialViewHeadingDegrees"])
            if "EXIF:InitialViewPitchDegrees" in exif:
                self.initial_pitch_degrees = float(exif["EXIF:InitialViewPitchDegrees"])
            if "EXIF:InitialViewRollDegrees" in exif:
                self.initial_roll_degrees = float(exif["EXIF:InitialViewRollDegrees"])
            if pose_heading != 0 or pose_pitch != 0 or pose_roll != 0:
                logger.info(
                    f"Pose heading, pitch, roll = ({degrees(pose_heading)}, {degrees(pose_pitch)}, {degrees(pose_roll)})")
                self.pcm_R_geo = self._pcm_rot_geo(pose_heading, pose_pitch, pose_roll)

    @staticmethod
    def _pcm_rot_geo(heading: float, pitch: float, roll: float):
        pcm_rot_geo = numpy.array([
            [cos(roll), -sin(roll), 0],
            [sin(roll), cos(roll), 0],
            [0, 0, 1],
        ], dtype=numpy.float32)
        pcm_rot_geo = pcm_rot_geo @ [
            [1, 0, 0],
            [0, cos(pitch), sin(pitch)],
            [0, -sin(pitch), cos(pitch)],
        ]
        pcm_rot_geo = pcm_rot_geo @ [
            [cos(heading), 0, sin(heading)],
            [0, 1, 0],
            [-sin(heading), 0, cos(heading)],
        ]
        return pcm_rot_geo


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
