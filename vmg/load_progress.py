import enum


class LoadProgress(enum.Enum):
    """Values are estimates of percent complete"""
    NONE = 0
    OBJECT_CREATED = 2
    FILE_OPENED = 4
    METADATA_LOADED = 15
    ARRAY_CREATED = 40
    TILES_CREATED = 65
    TILES_UPLOADED = 90
    DISPLAYED = 100
    ERROR = -999
