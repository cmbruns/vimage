import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget
from PySide6.QtCore import QSettings, QStandardPaths, QDir, QFileInfo


# The exhaustive list of extensions your app scanning logic supports
SUPPORTED_EXTENSIONS = {
    ".bmp", ".dng", ".heic", ".heif", ".gif",
    ".pbm", ".pgm", ".ppm", ".png", ".jpg",
    ".jpeg", ".tif", ".tiff", ".webp"
}

# Unified Open Filter string mapping every single format out-of-the-box
OPEN_IMAGE_FILTERS = (
    "Supported Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.bmp *.gif *.pbm *.pgm *.ppm *.dng *.heic *.heif);;"
    "PNG Images (*.png);;"
    "JPEG Images (*.jpg *.jpeg);;"
    "TIFF Images (*.tif *.tiff);;"
    "WEBP Images (*.webp);;"
    "BMP Images (*.bmp);;"
    "PPM Images (*.ppm *.pgm *.pbm);;"
    "GIF Images (*.gif);;"
    "All files (*)"
)

# Standardized Save Filters matching your exact specification safely
SAVE_IMAGE_FILTERS = (
    "PNG Images (*.png);;"
    "JPEG Images (*.jpg *.jpeg);;"
    "TIFF Images (*.tif *.tiff);;"
    "WEBP Images (*.webp);;"
    "BMP Images (*.bmp);;"
    "PPM Images (*.ppm *.pgm *.pbm);;"
    "GIF Images (*.gif);;"
    "All files (*)"
)


class ImageFileDialogManager:
    def __init__(self, company_name: str = "MyCompany", app_name: str = "ImageViewer"):
        self.settings = QSettings(company_name, app_name)

    @staticmethod
    def _is_valid_and_writable(path: str) -> bool:
        if not path:
            return False
        info = QFileInfo(path)
        return info.exists() and info.isDir() and info.isWritable()

    def get_deterministic_directory(self, is_save_mode: bool, provenance_path: str = "") -> str:
        if provenance_path:
            provenance_dir = QFileInfo(provenance_path).absolutePath()
            if self._is_valid_and_writable(provenance_dir):
                return provenance_dir

        history_keys = (
            ["history/last_saved_dir", "history/last_browsed_dir"]
            if is_save_mode else
            ["history/last_browsed_dir", "history/last_saved_dir"]
        )

        for key in history_keys:
            path = self.settings.value(key, "")
            assert isinstance(path, str)
            if self._is_valid_and_writable(path):
                return path

        pics_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        if self._is_valid_and_writable(pics_dir):
            return pics_dir

        docs_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if self._is_valid_and_writable(docs_dir):
            return docs_dir

        home_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        if self._is_valid_and_writable(home_dir):
            return home_dir

        return QDir.tempPath()

    @staticmethod
    def scan_folder_for_images(folder_path: str) -> list[Path]:
        """Uses your scanning filter to deterministically pull valid paths."""
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []

        # Leverages your exact targeted lower-case extension tracking logic safely
        return [
            file for file in folder.iterdir()
            if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    def open_image(self, parent: QWidget) -> str:
        """Opens dialog using smart composite filter mapping instead of raw '*.*'"""
        initial_dir = self.get_deterministic_directory(is_save_mode=False)

        # PySide6 static calls return a tuple: (chosen_file_path, filter_used)
        file_path, _ = QFileDialog.getOpenFileName(
            parent=parent,
            caption="Choose an image file",
            dir=initial_dir,
            filter=OPEN_IMAGE_FILTERS
        )

        if file_path:
            browsed_dir = QFileInfo(file_path).absolutePath()
            self.settings.setValue("history/last_browsed_dir", browsed_dir)
            return file_path
        return ""

    def save_image_as(self, parent: QWidget, provenance_path: str = "", default_name: str = "untitled.png") -> str:
        """Saves file while correctly maintaining matching initial selectedFilter mappings."""
        initial_dir = self.get_deterministic_directory(is_save_mode=True, provenance_path=provenance_path)
        initial_file_path = os.path.join(initial_dir, default_name)

        # PySide6 static calls return a tuple: (target_file_path, filter_used)
        file_path, _ = QFileDialog.getSaveFileName(
            parent=parent,
            caption="Save Image As",
            dir=initial_file_path,
            filter=SAVE_IMAGE_FILTERS,
            selectedFilter="PNG Images (*.png)"  # Fixed syntax to match filter string precisely
        )

        if file_path:
            saved_dir = QFileInfo(file_path).absolutePath()
            self.settings.setValue("history/last_saved_dir", saved_dir)
            self.settings.setValue("history/last_browsed_dir", saved_dir)
            return file_path
        return ""
