from PySide6.QtCore import QPoint

from vmg.coordinate import BasicVec2, BasicVec3


class DimensionsOmp(BasicVec2):
    pass


class DimensionsQwn(BasicVec2):
    pass


class LocationHpd(BasicVec2):
    """
    Heading and pitch in degrees.
    Heading is measured in degrees clockwise from north.
    Pitch is measured as degrees above the horizon.
    """
    def __init__(self, heading: float, pitch: float) -> None:
        super().__init__(heading, pitch)

    def __repr__(self):
        return f"{self.__class__.__name__}(heading={self.x}, pitch={self.y})"

    def __str__(self):
        return f"(heading={self.x:.1f}°, pitch={self.y:.1f}°)"

    @property
    def heading(self):
        """Angle clockwise from north in degrees"""
        return self.x

    @property
    def pitch(self):
        """Angle above horizon in degrees"""
        return self.y


class LocationObq(BasicVec3):
    pass


class LocationNic(BasicVec3):
    pass


class LocationOmp(BasicVec3):
    pass


class LocationOnt(BasicVec3):
    pass


class LocationPrj(BasicVec3):
    pass


class LocationQwn(BasicVec3):
    @staticmethod
    def from_qpoint(qpoint: QPoint) -> "LocationQwn":
        return LocationQwn(qpoint.x(), qpoint.y(), 1)


class LocationRelative(BasicVec2):
    pass
