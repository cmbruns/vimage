from typing import Any, Protocol


class RenderStateLike(Protocol):
    """Minimal interface for the view/controller state used by shaders and DNG rendering."""

    brightness: float
    pixel_filter: Any
    display_projection: Any
    ont_rot_obq: Any
    raw_rot_ont: Any
    input_is_linear: bool
    window_size: Any
    zoom: float
    input_format: Any
    sel_rect: Any
    background_color: Any

    def ndc_xform_omp(self) -> Any:
        ...

    def omp_scale_qwn(self) -> float:
        ...
