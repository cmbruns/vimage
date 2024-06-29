"""
https://stackoverflow.com/questions/67904300/how-to-get-file-thumbnail-from-windows-cache-through-python
"""

from ctypes import POINTER, byref, cast, windll, c_void_p, c_wchar_p

import numpy
from ctypes.wintypes import SIZE, UINT, HANDLE, HBITMAP

from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from PIL import Image
import win32ui

from vmg.performance import ElapsedTime

shell32 = windll.shell32
shell32.SHCreateItemFromParsingName.argtypes = [c_wchar_p, c_void_p, POINTER(GUID), POINTER(HANDLE)]
shell32.SHCreateItemFromParsingName.restype = HRESULT

SIIGBF_RESIZETOFIT = 0  # noqa


class IShellItemImageFactory(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{bcc18b79-ba16-442f-80c4-8a59c30c463b}')
    _idlflags_ = []  # noqa


IShellItemImageFactory._methods_ = [
    COMMETHOD(
        [],
        HRESULT,
        'GetImage',
        (['in'], SIZE, 'size'),
        (['in'], UINT, 'flags'),
        (['out'], POINTER(HBITMAP), 'phbm')  # noqa
    ),]

LP_IShellItemImageFactory = POINTER(IShellItemImageFactory)


def get_win32_thumbnail(filename, icon_size=96) -> HBITMAP:
    """ Returns thumbnail image as HBITMAP"""
    h_shell_item_image_factory = HANDLE()
    hr = shell32.SHCreateItemFromParsingName(
        filename,
        0,
        byref(IShellItemImageFactory._iid_),  # noqa
        byref(h_shell_item_image_factory),
    )
    if hr < 0:
        raise Exception(f'SHCreateItemFromParsingName failed: {hr}')
    h_shell_item_image_factory = cast(h_shell_item_image_factory, LP_IShellItemImageFactory)
    # Raises exception on failure.
    h_bitmap = h_shell_item_image_factory.GetImage(SIZE(icon_size, icon_size), SIIGBF_RESIZETOFIT)
    py_c_bitmap = win32ui.CreateBitmapFromHandle(h_bitmap)
    info = py_c_bitmap.GetInfo()
    data = py_c_bitmap.GetBitmapBits(True)
    w, h = info['bmWidth'], info['bmHeight']
    depth = int(len(data) / w / h)
    numpy_array = numpy.ndarray(shape=(h, w, depth), dtype=numpy.uint8, buffer=data)
    pil_image = Image.frombuffer('RGB', (w, h), data, 'raw', 'BGRX', 0, 1)
    return pil_image


if __name__ == "__main__":
    with ElapsedTime():
        img = get_win32_thumbnail(
            filename=r"C:\Users\cmbruns\Pictures\_Bundles_for_Berlin__More_production!.jpg",
        )
    print(img)
