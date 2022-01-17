from enum import Enum


class PixelFilter(Enum):
    SHARP = 1
    BILINEAR = 2
    HERMITE = 3
    CATMULL_ROM = 4