from abc import ABC, abstractmethod
from typing import Any, Protocol, Optional

import numpy
from numpy.typing import NDArray
from PIL import Image

from vmg.display_projection import DisplayProjection
from vmg.load_progress import LoadProgress
from vmg.pixel_filter import PixelFilter


Float = float  # Make inspection stfu about "| int"
GLint = int


class ImageMetadataLike(Protocol):
    file_name: Optional[str]


class ImageSignallerLike(Protocol):
    pass


class ImageLike(Protocol):
    """A loaded image with GL lifecycle and tile emission."""
    sq: ImageSignallerLike
    md: ImageMetadataLike
    tiles: list[TileLike]
    load_progress: LoadProgress
    array: NDArray
    pil_image: Optional[Image.Image]

    def initialize_gl(self) -> None:
        ...


class ShaderProgramLike(ABC):
    """A GL shader program."""

    @abstractmethod
    def initialize_gl(self) -> None:
        """Compile GL program."""

    @abstractmethod
    def paint_gl(self, render_state: "RenderStateLike", image: ImageLike) -> None:
        """Bind program, set uniforms, and render tiles."""


class TileLike(Protocol):
    """A rectangular region of an image backed by a GL texture."""
    uv_bounds: tuple[Float, Float, Float, Float]

    def is_ready(self) -> bool:
        ...

    def paint_gl(self, view_state: RenderStateLike) -> bool:
        """Bind textures and VBOs and issue draw calls."""

    @property
    def tile_X_img(self) -> NDArray[numpy.floating]:
        """3×3 float32 transform from tile to image space."""
        ...


class RenderStateLike(Protocol):
    """Minimal interface for the view/controller state used by shaders."""

    anisotropic_filtering: bool
    show_tile_boundaries: bool
    texture_wrap: GLint

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
    def ndc_xform_opx(self) -> NDArray[numpy.floating]:
        """Return 3×3 transform from OMP to NDC."""
        ...

    @abstractmethod
    def opx_scale_qwn(self) -> Float:
        """Return scale factor for OMP → QWN."""
        ...
