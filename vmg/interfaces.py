from abc import ABC, abstractmethod
from typing import Any, Iterator

import numpy
from numpy.typing import NDArray

from vmg.display_projection import DisplayProjection
from vmg.exif_orientation import ExifOrientation
from vmg.frame import DimensionsOmp
from vmg.metadata import InputFormat, PhotometricScale
from vmg.pixel_filter import PixelFilter


Float = float  # Make inspection stfu about "| int"


class ImageLike(ABC):
    """A loaded image with GL lifecycle and tile emission."""

    # --- Required attributes (getter + setter) ---

    @property
    @abstractmethod
    def array(self) -> NDArray:
        ...

    @property
    @abstractmethod
    def file_name(self) -> str:
        ...

    @property
    @abstractmethod
    def input_format(self) -> InputFormat:
        ...

    # Setter because user can manually change input format
    @input_format.setter
    @abstractmethod
    def input_format(self, value: InputFormat) -> None:
        ...

    @property
    @abstractmethod
    def orientation(self) -> ExifOrientation:
        ...

    @property
    @abstractmethod
    def photometric_scale(self) -> PhotometricScale:
        ...

    @property
    @abstractmethod
    def raw_rot_ont(self) -> NDArray[numpy.floating]:
        """3×3 float32 pano camera orientation matrix."""
        ...

    @property
    @abstractmethod
    def size_omp(self) -> DimensionsOmp:
        ...

    @property
    @abstractmethod
    def size_raw(self) -> tuple[int, int]:
        ...

    # --- Required methods ---

    @abstractmethod
    def initialize_gl(self) -> None:
        """Create OpenGL resources in the loading thread"""

    @abstractmethod
    def paint_gl(self) -> None:
        """Display image in the UI thread"""

    @abstractmethod
    def tiles(self) -> Iterator[TileLike]:
        """Display image in the UI thread"""


class ShaderProgramLike(ABC):
    """A GL shader program."""

    @abstractmethod
    def initialize_gl(self) -> None:
        """Compile GL program."""

    @abstractmethod
    def paint_gl(self, render_state: "RenderStateLike", image: ImageLike) -> None:
        """Bind program, set uniforms, and render tiles."""


class TileLike(ABC):
    """A rectangular region of an image backed by a GL texture."""

    @property
    @abstractmethod
    def tile_X_img(self) -> NDArray[numpy.floating]:
        """3×3 float32 transform from tile to image space."""
        ...

    @tile_X_img.setter
    @abstractmethod
    def tile_X_img(self, value: NDArray[numpy.floating]) -> None:
        ...

    @abstractmethod
    def paint_gl(self) -> None:
        """Bind textures and VBOs and issue draw calls."""


class RenderStateLike(ABC):
    """Minimal interface for the view/controller state used by shaders."""

    # --- Required attributes ---

    @property
    @abstractmethod
    def brightness(self) -> Float:
        ...

    @brightness.setter
    @abstractmethod
    def brightness(self, value: Float) -> None:
        ...

    @property
    @abstractmethod
    def pixel_filter(self) -> PixelFilter:
        ...

    @pixel_filter.setter
    @abstractmethod
    def pixel_filter(self, value: PixelFilter) -> None:
        ...

    @property
    @abstractmethod
    def display_projection(self) -> DisplayProjection:
        ...

    @display_projection.setter
    @abstractmethod
    def display_projection(self, value: DisplayProjection) -> None:
        ...

    @property
    @abstractmethod
    def ont_rot_obq(self) -> NDArray[numpy.floating]:
        """3×3 float32 pano view rotation."""
        ...

    @ont_rot_obq.setter
    @abstractmethod
    def ont_rot_obq(self, value: NDArray[numpy.floating]) -> None:
        ...

    @property
    @abstractmethod
    def window_size(self) -> Any:
        ...

    @window_size.setter
    @abstractmethod
    def window_size(self, value: Any) -> None:
        ...

    @property
    @abstractmethod
    def zoom(self) -> Float:
        ...

    @zoom.setter
    @abstractmethod
    def zoom(self, value: Float) -> None:
        ...

    @property
    @abstractmethod
    def sel_rect(self) -> Any:
        ...

    @sel_rect.setter
    @abstractmethod
    def sel_rect(self, value: Any) -> None:
        ...

    @property
    @abstractmethod
    def background_color(self) -> Any:
        ...

    @background_color.setter
    @abstractmethod
    def background_color(self, value: Any) -> None:
        ...

    # --- Required methods ---

    @abstractmethod
    def ndc_xform_omp(self) -> NDArray[numpy.floating]:
        """Return 3×3 transform from OMP to NDC."""
        ...

    @abstractmethod
    def omp_scale_qwn(self) -> Float:
        """Return scale factor for OMP → QWN."""
        ...
