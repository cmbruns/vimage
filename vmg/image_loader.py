from math import floor
from os import access, R_OK
from os.path import isfile
import time

import numpy
from PIL import ExifTags, Image
from PySide6 import QtCore
from PySide6.QtCore import Qt
from skimage.transform import resize


class Performance(object):
    def __init__(self, indent=0):
        self.indent = indent
        self.begin = time.time()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        end = time.time()
        elapsed = end - self.begin
        print(f"{self.indent * ' '}elapsed time = {elapsed:.3f}")


class ImageData(QtCore.QObject):
    def __init__(self, parent, file_name: str):
        super().__init__(parent=parent)
        self.file_name = str(file_name)
        self.existence_checked = False
        self.pil_image = None
        self.numpy_image = None
        self.exif = {}
        self.xmp = {}


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.file_name = None
        # Connect the loading process via a series of signals,
        # so the process can be interrupted when a new file is requested
        self.file_name_changed.connect(self.check_existence, Qt.QueuedConnection)
        self.existence_checked.connect(self.open_pil_image, Qt.QueuedConnection)
        self.pil_image_opened.connect(self.load_metadata, Qt.QueuedConnection)
        self.metadata_loaded.connect(self.create_numpy_image, Qt.QueuedConnection)
        # maybe later...
        # self.numpy_image_created.connect(self.create_mipmaps, Qt.QueuedConnection)

    def _name_matches(self, file_name) -> bool:
        if self.file_name != file_name:
            print(" Name changed!")
            return False
        return True

    load_failed = QtCore.Signal(str)

    @QtCore.Slot(str)  # noqa
    def load_file_name(self, file_name: str):
        print(f" load_file_name {file_name}")
        image_data = ImageData(self, file_name)
        self.file_name = file_name
        self.file_name_changed.emit(image_data)

    file_name_changed = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def check_existence(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        print(f"  Checking existence of {file_name}")
        if not isfile(file_name):
            self.load_failed.emit(file_name)
            return
        if not access(file_name, R_OK):
            self.load_failed.emit(file_name)
            return
        image_data.existence_checked = True
        self.existence_checked.emit(image_data)

    existence_checked = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def open_pil_image(self, image_data):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        print(f"   Creating PIL Image for {file_name}")
        with Performance(indent=3):
            pil_image = Image.open(file_name)
            if pil_image.width < 1 or pil_image.height < 1:
                self.load_failed.emit(file_name)
                return
            image_data.pil_image = pil_image
        self.pil_image_opened.emit(image_data)

    pil_image_opened = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)
    def load_metadata(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        print(f"    Loading image metadata for {file_name}")
        pil_image = image_data.pil_image
        exif0 = pil_image.getexif()
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in exif0.items()
            if k in ExifTags.TAGS
        }
        for ifd_id in ExifTags.IFD:
            try:
                ifd = exif0.get_ifd(ifd_id)
                if ifd_id == ExifTags.IFD.GPSInfo:
                    resolve = ExifTags.GPSTAGS
                else:
                    resolve = ExifTags.TAGS
                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    exif[tag] = v
            except KeyError:
                pass
        try:
            xmp = pil_image.getxmp()  # noqa
        except AttributeError:
            xmp = {}
        image_data.xmp = xmp
        image_data.exif = exif
        self.metadata_loaded.emit(image_data)

    metadata_loaded = QtCore.Signal(ImageData)

    @staticmethod
    def _linear_from_srgb(image: numpy.array):
        return numpy.where(image >= 0.04045, ((image + 0.055) / 1.055)**2.4, image/12.92)

    @QtCore.Slot(str, Image.Image)
    def create_numpy_image(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        print(f"     Creating numpy data for {file_name}")
        with Performance(5):
            # TODO: Should this be earlier?
            if image_data.pil_image.mode == "P":
                image_data.pil_image = image_data.pil_image.convert("RGBA")
            pil_image = image_data.pil_image
            numpy_image = numpy.array(pil_image)
            # Normalize values to maximum 1.0 and convert to float32
            # TODO: test performance
            max_values = {
                numpy.dtype("bool"): 1,
                numpy.dtype("uint8"): 255,
                numpy.dtype("uint16"): 65535,
                numpy.dtype("float32"): 1.0,
            }
            numpy_image = numpy_image.astype(numpy.float32) / max_values[numpy_image.dtype]
            # Convert srgb value scale to linear
            if len(numpy_image.shape) == 2:
                # Monochrome image
                numpy_image = self._linear_from_srgb(numpy_image)
            else:
                for rgb in range(3):
                    numpy_image[:, :, rgb] = self._linear_from_srgb(numpy_image[:, :, rgb])  # approximate srgb -> linear
            # Use premultiplied alpha for better filtering
            if pil_image.mode == "RGBA":
                a = numpy_image
                alpha_layer = a[:, :, 3]
                for rgb in range(3):
                    a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
            image_data.numpy_image = numpy_image
        self.numpy_image_created.emit(image_data)

    numpy_image_created = QtCore.Signal(ImageData)

    @staticmethod
    def _mipmap_dim(base: int, level: int) -> int:
        return max(1, int(floor(base / 2**level)))

    @QtCore.Slot(ImageData)
    def create_mipmaps(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        print(f"      Creating mipmaps for {file_name}")
        h, w = image_data.numpy_image.shape[:2]
        base_size = (w, h)
        size = [w, h]
        level = 0
        mipmap = image_data.numpy_image
        image_data.mipmaps = []
        while size[0] > 1 or size[1] > 1:
            level += 1
            size = [self._mipmap_dim(x, level) for x in base_size]
            mipmap = resize(mipmap, size)
            image_data.mipmaps.append(mipmap)
        self.mipmaps_created.emit(image_data)

    mipmaps_created = QtCore.Signal(ImageData)

