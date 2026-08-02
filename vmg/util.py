__all__ = [
    "sin_from_equi8",
]

from typing import Optional

import platform
from ctypes import c_size_t, c_uint8, cdll, POINTER
import numpy

from vmg.resources import resource_filename

if platform.system() == "Windows":
    library_path = resource_filename("vmg.lib", "vimage_util.dll")
else:
    raise NotImplementedError

vimage_util_library = cdll.LoadLibrary(library_path)


# void sin_from_equi_u8(const uint8_t* src, uint8_t* dst, size_t nRows, size_t nCols, size_t nChans)
# noinspection PyDeprecation
vimage_util_library.sin_from_equi_u8.argtypes = [
    POINTER(c_uint8),  # src
    POINTER(c_uint8),  # dst
    c_size_t,  # nRows
    c_size_t,  # nCols
    c_size_t  # nChans
]
vimage_util_library.sin_from_equi_u8.restype = None


# 4. Public Python Wrapper (In-place or Copy behavior)
def sin_from_equi8(
        src_array: numpy.ndarray,
        dst_array: Optional[numpy.ndarray] = None,
) -> numpy.ndarray:
    assert src_array.flags['C_CONTIGUOUS']
    if src_array is dst_array:
        assert src_array.flags['WRITEABLE']
        dst_array = src_array
    elif dst_array is None:
        dst_array = numpy.empty_like(src_array)
    nRows, nCols = src_array.shape[0:2]
    if len(src_array.shape) == 3:
        nChans = src_array.shape[2]
    else:
        nChans = 1
    assert src_array.dtype == numpy.uint8
    # noinspection PyDeprecation
    src_ptr = src_array.ctypes.data_as(POINTER(c_uint8))
    # noinspection PyDeprecation
    dst_ptr = dst_array.ctypes.data_as(POINTER(c_uint8))
    vimage_util_library.sin_from_equi_u8(src_ptr, dst_ptr, nRows, nCols, nChans)
    return dst_array


# 5. Local smoke test execution
if __name__ == "__main__":
    print(f"Testing bindings against binary: {library_path}")

    # Create a dummy 16x16 pixel RGB image filled with 1s
    # Ensuring C_CONTIGUOUS out of the box
    test_image = numpy.random.randint(0, 256, (8, 16), dtype=numpy.uint8)
    print(test_image)

    print(f"Source Array Shape: {test_image.shape}, Dtype: {test_image.dtype}")
    print(f"Memory packed (Contiguous): {test_image.flags['C_CONTIGUOUS']}")

    # If your C++ function isn't fully implemented yet, this will just call it.
    # Ensure your C++ template writes something back to 'dst' to prove it ran!
    output_image = sin_from_equi8(test_image)
    print(output_image)
    print("Success! Native function executed cleanly without crashing ctypes.")
