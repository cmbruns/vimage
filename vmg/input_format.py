from enum import Enum


class InputFormat(Enum):
    EQUIRECTANGULAR = 0   # stitched pano
    DUAL_FISHEYE = 1      # raw fisheye pair
    STANDARD_PHOTO = 2       # normal 2D photo
