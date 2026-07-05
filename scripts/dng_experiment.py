import tifffile

from vmg.texture import Texture

file_name = "C:/Users/cmbruns/Pictures/360CameraSamples/XiaomiMisphere/IMG_20260704_105506.DNG"
with tifffile.TiffFile(file_name) as tif:
    page = tif.pages[0]
    raw = page.asarray()
    # raw = tifffile.imread(file_name)
    print(raw.shape, raw.dtype)
    print(raw)
    texture = Texture.from_numpy(raw)
