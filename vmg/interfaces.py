from abc import ABC, abstractmethod
from typing import Protocol, Iterable, Any

import numpy
from numpy.typing import NDArray

from vmg.display_projection import DisplayProjection
from vmg.frame import DimensionsOmp
from vmg.input_format import InputFormat
from vmg.photometric_scale import PhotometricScale
from vmg.pixel_filter import PixelFilter


Float = float


class ImageLike(ABC):
    """A loaded image with GL lifecycle and tile emission."""

    # --- Required attributes (getter + setter) ---

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
    def file_name(self) -> str:
        ...

    @property
    @abstractmethod
    def photometric_scale(self) -> PhotometricScale:
        ...

    @property
    @abstractmethod
    def raw_rot_ont(self) -> NDArray:
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
        """Create GL textures."""

    @abstractmethod
    def tiles(self) -> Iterable[TileLike]:
        """Emit tiles covering this image."""


class ShaderProgramLike(Protocol):
    """A GL shader program"""
    def initialize_gl(self) -> None:
        """Compile GL program"""

    def paint_gl(self, render_state: RenderStateLike, image: ImageLike):
        """Bind program, set uniforms, and render tiles"""


class TileLike(Protocol):
    """A rectangular region of an image backed by a GL texture."""
    tile_X_img: NDArray[numpy.float32]  # shape (3, 3)

    def paint_gl(self):
        """Bind textures and vbos and issue draw calls"""


class RenderStateLike(Protocol):
    """Minimal interface for the view/controller state used by shaders and DNG rendering."""

    brightness: Float
    pixel_filter: PixelFilter
    display_projection: DisplayProjection
    ont_rot_obq: NDArray[numpy.float32]  # shape (3, 3)  pano view rotation
    # input_is_linear: bool  # Should be ImageLike?
    window_size: Any
    zoom: Float
    # input_format: Any  # Should be ImageLike?
    sel_rect: Any
    background_color: Any

    def ndc_xform_omp(self) -> NDArray[numpy.float32]:  # shape (3, 3)
        ...

    def omp_scale_qwn(self) -> Float:
        ...
