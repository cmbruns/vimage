from numbers import Number

import enum

from abc import ABC, abstractmethod
from typing import Any, Protocol, Optional

import numpy
from numpy.typing import NDArray
from PIL import Image

from vmg.display_projection import DisplayProjection
from vmg.exif_orientation import ExifOrientation
from vmg.load_progress import LoadProgress
from vmg.pixel_filter import PixelFilter, PixelNumerals
from vmg.selection_box import SelectionBox

Float = float  # Make inspection stfu about "| int"
GLint = int


class ImageMetadataLike(Protocol):
    as_shot_neutral: tuple[Float, Float, Float]
    baseline_exposure: Float
    black_level: tuple[Float, Float, Float]
    channel_count: int
    data_max: Number
    df_lens_rot_radians: Float
    file_name: Optional[str]
    input_format: InputFormat
    inscribed_fov_radians: Float
    is_dng: bool
    lsr_X_wba: NDArray[numpy.float32]
    orientation: ExifOrientation
    pcm_R_geo: NDArray[numpy.float32]
    photometric_scale: PhotometricScale
    rpx_R_opx: NDArray[numpy.float32]
    size_rpx: tuple[int, int]
    upper_bound: Number
    white_level: tuple[Float, Float, Float]

    def load_exiftool(self, file_name: str) -> None:
        ...

    def load_pil_image(self, pil_image: Image.Image) -> None:
        ...


class ImageSignallerLike(Protocol):
    pass


class RenderStateLike(Protocol):
    """Minimal interface for the view/controller state used by shaders."""

    anisotropic_filtering: bool
    brightness: Float
    display_projection: DisplayProjection
    pixel_filter: PixelFilter
    pixel_numerals: PixelNumerals
    sel_rect: SelectionBox
    show_tile_boundaries: bool
    texture_wrap: GLint

    @property
    def geo_rot_usr(self) -> NDArray[numpy.float32]:
        ...

    @property
    @abstractmethod
    def window_size(self) -> Any:
        ...

    @property
    @abstractmethod
    def zoom(self) -> Float:
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


class ShaderProgramLike(ABC):
    """A GL shader program."""

    @abstractmethod
    def initialize_gl(self) -> None:
        """Compile GL program."""

    @abstractmethod
    def paint_gl(self, render_state: "RenderStateLike", image: TiledImageLike) -> None:
        """Bind program, set uniforms, and render tiles."""


class TiledImageLike(Protocol):
    """A loaded image with GL lifecycle and tile emission."""
    sq: ImageSignallerLike
    md: ImageMetadataLike
    tiles: list[TileLike]
    load_progress: LoadProgress
    array: Optional[NDArray]
    pil_image: Optional[Image.Image]

    def initialize_gl(self) -> None:
        ...

    def paint_gl(self, program: ShaderProgramLike, view_state: RenderStateLike) -> None:
        ...

    def set_display_complete(self) -> None:
        ...


class TileLike(Protocol):
    """A rectangular region of an image backed by a GL texture."""

    texture_id: Optional[GLint]
    uv_bounds: tuple[Float, Float, Float, Float]
    vao: Optional[GLint]

    def is_ready(self) -> bool:
        ...

    # def paint_gl(self, view_state: RenderStateLike) -> bool:
    #     """Bind textures and VBOs and issue draw calls."""

    @property
    def tile_X_img(self) -> NDArray[numpy.floating]:
        """3×3 float32 transform from tile to image space."""
        ...


class InputFormat(enum.Enum):
    EQUIRECTANGULAR = 0   # stitched pano
    DUAL_FISHEYE = 1      # raw fisheye pair
    STANDARD_PHOTO = 2    # normal 2D photo
    SINUSOIDAL = 3        #


class PhotometricScale(enum.Enum):
    LINEAR = 0
    SRGB = 1
