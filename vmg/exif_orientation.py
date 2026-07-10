import enum


class ExifOrientation(enum.Enum):
    """Names describe the transformation from raw to oriented"""
    UNSPECIFIED = 0
    ROTATE_0 = 1
    FLIP_HORIZONTAL = 2
    ROTATE_180 = 3
    FLIP_VERTICAL = 4
    FLIP_HORIZONTAL_ROTATE_90_CCW = 5
    ROTATE_90_CW = 6
    FLIP_HORIZONTAL_ROTATE_90_CW = 7
    ROTATE_90_CCW = 8
