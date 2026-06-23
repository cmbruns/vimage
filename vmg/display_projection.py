from enum import Enum


# Please keep these in sync with sphere.frag
class DisplayProjection(Enum):
    # Start with zero to match QCombobox numbering
    GNOMONIC = 0  # perspective view
    STEREOGRAPHIC = 1
    EQUIDISTANT = 2
    EQUIRECTANGULAR = 3
