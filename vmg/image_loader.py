from math import cos, radians, sin
from os import access, R_OK
from os.path import isfile
import time

import numpy
from PIL import ExifTags, Image
from PySide6 import QtCore
from PySide6.QtCore import Qt

from vmg.frame import DimensionsOmp


class Performance(object):
    def __init__(self, indent=0, message="", do_report=True):
        self.indent = indent
        self.begin = time.time()
        self.message = message
        self.do_report = do_report

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        end = time.time()
        _elapsed = end - self.begin
        if self.do_report:
            print(f"{self.indent * ' '}{self.message} elapsed time = {_elapsed * 1000:.1f} ms")


class ImageData(QtCore.QObject):
    def __init__(self, file_name: str, parent=None):
        super().__init__(parent=parent)
        self.file_name = str(file_name)
        self.pil_image = None
        self.numpy_image = None
        self.exif = {}
        self.xmp = {}
        self.size_raw = [0, 0]
        self.size_omp = DimensionsOmp(0, 0)
        self._raw_rot_ont = numpy.eye(3, dtype=numpy.float32)
        self._raw_rot_omp = numpy.eye(2, dtype=numpy.float32)
        self._is_360 = False

    def file_is_readable(self) -> bool:
        file_name = self.file_name
        if not isfile(file_name):
            return False
        if not access(file_name, R_OK):
            return False
        return True

    @property
    def is_360(self) -> bool:
        return self._is_360

    def open_pil_image(self) -> bool:
        try:
            self.pil_image = Image.open(self.file_name)
            return True
        except ...:
            return False

    @property
    def raw_rot_omp(self) -> numpy.array:
        return self._raw_rot_omp

    @property
    def raw_rot_ont(self) -> numpy.array:
        return self._raw_rot_ont

    @property
    def size(self) -> DimensionsOmp:
        return self.size_omp

    exif_orientation_to_matrix = {
        1: numpy.array([[1, 0], [0, 1]], dtype=numpy.float32),
        2: numpy.array([[-1, 0], [0, 1]], dtype=numpy.float32),
        3: numpy.array([[-1, 0], [0, -1]], dtype=numpy.float32),
        4: numpy.array([[1, 0], [0, -1]], dtype=numpy.float32),
        5: numpy.array([[0, 1], [1, 0]], dtype=numpy.float32),
        6: numpy.array([[0, 1], [-1, 0]], dtype=numpy.float32),
        7: numpy.array([[0, -1], [-1, 0]], dtype=numpy.float32),
        8: numpy.array([[0, -1], [1, 0]], dtype=numpy.float32),
    }


class ImageLoader(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.file_name = None
        # Connect the loading process via a series of signals,
        # so the process can be interrupted when a new file is requested
        self.file_name_changed.connect(self.check_existence, Qt.QueuedConnection)  # noqa
        self.existence_checked.connect(self.open_pil_image, Qt.QueuedConnection)  # noqa
        self.pil_image_opened.connect(self.use_pil_image, Qt.QueuedConnection)  # noqa
        self.pil_image_assigned.connect(self.use_pil_image, Qt.QueuedConnection)  # noqa
        self.pil_image_used.connect(self.load_metadata, Qt.QueuedConnection)  # noqa
        self.metadata_loaded.connect(self.create_numpy_image, Qt.QueuedConnection)  # noqa

    def _name_matches(self, file_name) -> bool:
        if self.file_name != file_name:
            # print(" Name changed!")
            return False
        return True

    load_failed = QtCore.Signal(str)

    @QtCore.Slot(str)  # noqa
    def load_file_name(self, file_name: str):
        # print(f" load_file_name {file_name}")
        image_data = ImageData(file_name, parent=self)
        self.file_name = file_name
        self.file_name_changed.emit(image_data)  # noqa

    file_name_changed = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def check_existence(self, image_data: ImageData):
        if not image_data.file_is_readable():
            self.load_failed.emit(image_data.file_name)  # noqa
            return
        self.existence_checked.emit(image_data)  # noqa

    existence_checked = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def open_pil_image(self, image_data):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        # print(f"   Creating PIL Image for {file_name}")
        with Performance(indent=3, do_report=False):
            if not image_data.open_pil_image():
                self.load_failed.emit(image_data.file_name)  # noqa
                return
        self.pil_image_opened.emit(image_data)  # noqa

    pil_image_opened = QtCore.Signal(ImageData)

    @QtCore.Slot(Image.Image, str)  # noqa
    def assign_pil_image(self, pil_image: Image.Image, file_name: str):
        """Load a PIL image without a corresponding file"""
        image_data = ImageData(file_name, parent=self)
        self.file_name = file_name
        image_data.pil_image = pil_image
        self.pil_image_assigned.emit(image_data)  # noqa

    pil_image_assigned = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def use_pil_image(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        pil_image = image_data.pil_image
        if pil_image.width < 1 or pil_image.height < 1:
            self.load_failed.emit(file_name)  # noqa
            return
        raw_width, raw_height = pil_image.size  # Unrotated dimension
        image_data.size_raw = (raw_width, raw_height)
        image_data.pil_image = pil_image
        self.pil_image_used.emit(image_data)  # noqa

    pil_image_used = QtCore.Signal(ImageData)

    @QtCore.Slot(ImageData)  # noqa
    def load_metadata(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        # print(f"    Loading image metadata for {file_name}")
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
        orientation_code: int = exif.get("Orientation", 1)
        image_data._raw_rot_omp = image_data.exif_orientation_to_matrix.get(orientation_code, numpy.eye(2, dtype=numpy.float32))
        image_data.size_omp = DimensionsOmp(*[abs(x) for x in (image_data.raw_rot_omp.T @ image_data.size_raw)])
        if image_data.size_omp.x == 2 * image_data.size_omp.y:
            try:
                image_data._is_360 = True
                try:
                    # TODO: InitialViewHeadingDegrees
                    desc = xmp["xmpmeta"]["RDF"]["Description"]
                    heading = radians(float(desc["PoseHeadingDegrees"]))
                    pitch = radians(float(desc["PosePitchDegrees"]))
                    roll = radians(float(desc["PoseRollDegrees"]))
                    m = numpy.array([
                        [cos(roll), -sin(roll), 0],
                        [sin(roll), cos(roll), 0],
                        [0, 0, 1],
                    ], dtype=numpy.float32)
                    m = m @ [
                        [1, 0, 0],
                        [0, cos(pitch), sin(pitch)],
                        [0, -sin(pitch), cos(pitch)],
                    ]
                    m = m @ [
                        [cos(heading), 0, sin(heading)],
                        [0, 1, 0],
                        [-sin(heading), 0, cos(heading)],
                    ]
                    image_data._raw_rot_ont = m
                except (KeyError, TypeError):
                    pass
                if exif["Model"].lower().startswith("ricoh theta"):
                    # print("360")
                    pass  # TODO 360 image
            except KeyError:
                pass
        else:
            image_data._is_360 = False
        self.metadata_loaded.emit(image_data)  # noqa

    metadata_loaded = QtCore.Signal(ImageData)

    @staticmethod
    def _linear_from_srgb(image: numpy.array):
        return numpy.where(image >= 0.04045, ((image + 0.055) / 1.055)**2.4, image/12.92)

    @QtCore.Slot(str, Image.Image)  # noqa
    def create_numpy_image(self, image_data: ImageData):
        file_name = image_data.file_name
        if not self._name_matches(file_name):
            return  # Latest file is something else
        # print(f"     Creating numpy data for {file_name}")
        with Performance(indent=5, do_report=False):
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
            # if len(numpy_image.shape) == 2:
            #     # Monochrome image
            #     numpy_image = self._linear_from_srgb(numpy_image)
            # else:
            #     for rgb in range(3):
            #         numpy_image[:, :, rgb] = self._linear_from_srgb(numpy_image[:, :, rgb])  # approximate srgb -> linear
            # Use premultiplied alpha for better filtering
            # if pil_image.mode == "RGBA":
            #     a = numpy_image
            #     alpha_layer = a[:, :, 3]
            #     for rgb in range(3):
            #         a[:, :, rgb] = (a[:, :, rgb] * alpha_layer).astype(a.dtype)
            image_data.numpy_image = numpy_image
        self.numpy_image_created.emit(image_data)  # noqa

    numpy_image_created = QtCore.Signal(ImageData)
