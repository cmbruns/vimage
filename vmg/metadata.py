import enum
import json
import logging
from math import atan2, cos, degrees, radians, sin
import re
import struct


import exiftool
import numpy
from numpy import linalg
import PIL
from PIL import ExifTags

from vmg.dng_color import LightSource, calculate_dng_t
from vmg.exif_orientation import ExifOrientation
from vmg.frame import DimensionsOmp

logger = logging.getLogger(__name__)


class InputFormat(enum.Enum):
    EQUIRECTANGULAR = 0   # stitched pano
    DUAL_FISHEYE = 1      # raw fisheye pair
    STANDARD_PHOTO = 2    # normal 2D photo
    SINUSOIDAL = 3        #


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
        self.pose_heading_degrees = 0.0
        self.pose_pitch_degrees = 0.0
        self.pose_roll_degrees = 0.0
        self._pcm_R_geo = numpy.eye(3, dtype=numpy.float32)
        # Dual fisheye lens parameters
        self.inscribed_fov_radians = radians(195.0)
        self.df_lens_rot_radians = radians(0.0)
        # Dng metadata
        self.black_level = (0.0, 0.0, 0.0)
        self.white_level = (1.0, 1.0, 1.0)
        self.as_shot_neutral = (1.0, 1.0, 1.0)
        self.color_matrix1 = numpy.eye(3, dtype=numpy.float32)
        self.color_matrix2 = None
        self.calibration_illuminant1 = LightSource.STANDARD_LIGHT_A
        self.calibration_illuminant2 = LightSource.D65
        # Convert camera sensor reference values to linear sRGB
        self.lsr_X_wba = numpy.eye(3, dtype=numpy.float32)
        self.baseline_exposure = 0.0

    @property
    def pcm_R_geo(self):
        return self._pcm_R_geo

    @pcm_R_geo.setter
    def pcm_R_geo(self, value):
        self._pcm_R_geo = value

    def load_tifffile_page(self, page):
        debug = False
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
                for d in desc_list:
                    if "PoseHeadingDegrees" in d:
                        self.pose_heading_degrees = float(d["PoseHeadingDegrees"])
                        is_pano = True
                    if "PosePitchDegrees" in d:
                        self.pose_pitch_degrees = float(d["PosePitchDegrees"])
                    if "PoseRollDegrees" in d:
                        self.pose_roll_degrees = float(d["PoseRollDegrees"])
                    if "InitialViewHeadingDegrees" in d:
                        self.initial_heading_degrees = float(d["InitialViewHeadingDegrees"])
                    if "InitialViewPitchDegrees" in d:
                        self.initial_pitch_degrees = float(d["InitialViewPitchDegrees"])
                    if "InitialViewRollDegrees" in d:
                        self.initial_roll_degrees = float(d["InitialViewRollDegrees"])
                Use360PanoReferenceConvention = False
                if Use360PanoReferenceConvention:
                    self.pose_roll_degrees = -self.pose_roll_degrees
                # Restrict to documented XMP range
                self.pose_roll_degrees = (self.pose_roll_degrees + 180.0) % 360.0 - 180.0
                self.pose_pitch_degrees = max(-90.0, min(90.0, self.pose_pitch_degrees))
                self.pose_heading_degrees = self.pose_heading_degrees % 360.0
                if self.pose_heading_degrees != 0 or self.pose_pitch_degrees != 0 or self.pose_roll_degrees != 0:
                    logger.info(
                        f"Pose heading, pitch, roll = ({self.pose_heading_degrees}, {self.pose_pitch_degrees}, {self.pose_roll_degrees})")
                self.update_pcm_rot_geo()
            except (KeyError, TypeError):
                pass

    def update_pcm_rot_geo(self):
        # Photographer's camera pose
        roll = radians(self.pose_roll_degrees)
        pitch = radians(self.pose_pitch_degrees)
        heading = radians(self.pose_heading_degrees)
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
        self.pcm_R_geo = pcm_rot_geo

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
        if "EXIF:ColorMatrix1" in exif:
            cm1 = exif["EXIF:ColorMatrix1"].split()
            assert len(cm1) == 9
            self.color_matrix1 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))
        if "EXIF:ColorMatrix2" in exif:
            cm1 = exif["EXIF:ColorMatrix2"].split()
            assert len(cm1) == 9
            self.color_matrix2 = numpy.array(cm1, dtype=numpy.float32).reshape((3, 3))
        if "EXIF:CalibrationIlluminant1" in exif:
            ci = LightSource(int(exif["EXIF:CalibrationIlluminant1"]))
            if ci == LightSource.UNKNOWN:
                logger.info("Unknown calibration illuminant")
            else:
                self.calibration_illuminant1 = ci
        if "EXIF:CalibrationIlluminant2" in exif:
            ci = LightSource(int(exif["EXIF:CalibrationIlluminant2"]))
            if ci == LightSource.UNKNOWN:
                logger.info("Unknown calibration illuminant")
            else:
                self.calibration_illuminant2 = ci
        if "EXIF:BaselineExposure" in exif:
            self.baseline_exposure = float(exif["EXIF:BaselineExposure"])
        # TODO: some dng might have a ForwardMatrix available...
        # Interpolate color matrix
        if self.color_matrix2 is None:
            rfv_X_d50 = self.color_matrix1
        else:
            dng_t = calculate_dng_t(
                self.as_shot_neutral,
                self.color_matrix1, self.color_matrix2,
                self.calibration_illuminant1, self.calibration_illuminant2,
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

        user_comment = ""
        if "EXIF:UserComment" in exif:
            user_comment = exif["EXIF:UserComment"]

        w, h = self.size_opx
        if w != 2 * h:
            self.input_format = InputFormat.STANDARD_PHOTO  # Non-2:1 aspect is always a regular photo
        else:  # Panorama
            if "EXIF:DNGVersion" in exif:
                self.input_format = InputFormat.DUAL_FISHEYE
            else:
                self.input_format = InputFormat.EQUIRECTANGULAR
            if "EXIF:PoseHeadingDegrees" in exif:
                self.pose_heading_degrees = float(exif["EXIF:PoseHeadingDegrees"])
            elif "EXIF:GPSImgDirection" in exif:
                self.pose_heading_degrees = float(exif["EXIF:GPSImgDirection"])
            if "EXIF:PosePitchDegrees" in exif:
                self.pose_pitch_degrees = float(exif["EXIF:PosePitchDegrees"])
            elif "Composite:RicohPitch" in exif:  # Ricoh Theta Z1 raw dng
                self.pose_pitch_degrees = float(exif["Composite:RicohPitch"])
            elif re.search(r'\sIMUHEX=([0-9a-fA-F]{36})\s', user_comment):  # QooCam3 Ultra raw dng
                m = re.search(r'\sIMUHEX=([0-9a-fA-F]{36})\s', user_comment)
                assert m
                imu_hex = m.group(1)
                self.pose_roll_degrees, self.pose_pitch_degrees = get_roll_pitch_from_imu(imu_hex)
            if "EXIF:PoseRollDegrees" in exif:
                self.pose_roll_degrees = float(exif["EXIF:PoseRollDegrees"])
            elif "Composite:RicohRoll" in exif:
                self.pose_roll_degrees = float(exif["Composite:RicohRoll"])
            if "EXIF:InitialViewHeadingDegrees" in exif:
                self.initial_heading_degrees = float(exif["EXIF:InitialViewHeadingDegrees"])
            if "EXIF:InitialViewPitchDegrees" in exif:
                self.initial_pitch_degrees = float(exif["EXIF:InitialViewPitchDegrees"])
            if "EXIF:InitialViewRollDegrees" in exif:
                self.initial_roll_degrees = float(exif["EXIF:InitialViewRollDegrees"])
            if self.pose_heading_degrees != 0 or self.pose_pitch_degrees != 0 or self.pose_roll_degrees != 0:
                logger.info(
                    f"Pose heading, pitch, roll = ({self.pose_heading_degrees}, {self.pose_pitch_degrees}, {self.pose_roll_degrees})")
                self.update_pcm_rot_geo()


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


def get_roll_pitch_from_imu(imu_hex_string: str):
    """
    Extracts the Roll angle in degrees from a 36-character QooCam3 IMU hex string.
    """

    # 2. Extract the 4 bytes controlling the Roll axis (Bytes 7 to 10)
    # Character indices: Bytes 7-8 are chars 12-16, Bytes 9-10 are chars 16-20
    roll_bytes_hex = imu_hex_string[12:20]
    binary_roll = bytes.fromhex(roll_bytes_hex)

    # 3. Unpack into two 16-bit signed integers (Little-Endian 'h')
    # val_y is the first pair, val_x is the second pair
    roll_y, roll_x = struct.unpack('<hh', binary_roll)
    # Avoid division by zero errors if both values are flattened
    if roll_x == 0 and roll_y == 0:
        roll_radians = 0.0
    else:
        roll_radians = atan2(-roll_y, -roll_x)
    roll_degrees = degrees(roll_radians) % 360
    if roll_degrees > 180:
        roll_degrees -= 360

    pitch_bytes_hex = imu_hex_string[20:28]
    binary_pitch = bytes.fromhex(pitch_bytes_hex)
    pitch_y, pitch_x = struct.unpack('<hh', binary_pitch)
    if pitch_x == 0 and pitch_y == 0:
        pitch_radians = 0.0
    elif pitch_x == 0:
        # Compute the shallow angle against the internal gravity constant
        pitch_radians = atan2(pitch_y, 16384)
    else:
        pitch_radians = atan2(pitch_y, pitch_x)
    pitch_degrees = degrees(pitch_radians)

    return roll_degrees, pitch_degrees


if __name__ == "__main__":
    # --- Quick Test Verification ---
    # Testing your stable 45-degree anchor string:
    print(f"Roll, Pitch: {get_roll_pitch_from_imu('000000000000808080800000000000000000')}°")
    # Target Output: 45.0°

    # Testing our calculated 10-degree target string:
    print(f"Roll, Pitch: {get_roll_pitch_from_imu('00000000000085E980800000000000000000')}°")
    # Target Output: 10.0°

    for imu in ("808080807BFF0000", "40404040e3061027",
                "2020202082e91027", "20204040a9358813",
                "404020206290c409", "808040407BFF0000",
                "404080807BFF0000", "52E2F00B7BFF0000",
                ):
        print(imu, get_roll_pitch_from_imu(f"000000000000{imu}00000000"))
