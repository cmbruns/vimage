from enum import Enum


# Please keep these in sync with sphere.frag
class Projection360(Enum):
    GNOMONIC = 0  # Start with zero to match QCombobox numbering
    STEREOGRAPHIC = 1
    EQUIDISTANT = 2
    EQUIRECTANGULAR = 3
