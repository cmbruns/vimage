import enum

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QSizePolicy


class ProgressState(enum.Enum):
    NO_IMAGE = 1,
    IMAGE_LOADING = 2,
    LOAD_FAILED = 3,
    LOAD_CANCELLED = 4,
    IMAGE_COMPLETE = 5,


class ProgressStatus(QtWidgets.QWidget):
    """
    Progress indicator for the main window status bar
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
        # status buttons
        # no image yet? folder icon to load an image
        self.open_button = QtWidgets.QToolButton()
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton)
        self.open_button.setIcon(icon)
        self.open_button.setToolTip("No image loaded. Click to open an image.")
        self.open_button.clicked.connect(self.open_image_requested)
        # image is loading, so show a cancel button
        self.cancel_button = QtWidgets.QToolButton()
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop)
        self.cancel_button.setIcon(icon)
        self.cancel_button.setToolTip("Image is loading. Click to cancel load.")
        self.cancel_button.clicked.connect(self.cancel_load_requested)
        # image load was cancelled
        self.cancelled_button = QtWidgets.QToolButton()
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_DialogCancelButton)
        self.cancelled_button.setIcon(icon)
        self.cancelled_button.setToolTip("Image loading was canceled.")
        # image loading is complete, show a green check mark
        self.done_label = QtWidgets.QLabel()
        self.done_label.setToolTip("Image load has completed.")
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton)
        pixmap = icon.pixmap(QtCore.QSize(16, 16))
        self.done_label.setPixmap(pixmap)
        # image loading failed, show a scary warning symbol
        self.failed_button = QtWidgets.QToolButton()
        self.failed_button.setToolTip("Image load failed. Click to view the log.")
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
        self.failed_button.setIcon(icon)
        self.failed_button.clicked.connect(self.view_log_requested)
        # progress bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumWidth(50)
        self.progress_bar.reset()
        # layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.open_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.cancelled_button)
        layout.addWidget(self.failed_button)
        layout.addWidget(self.done_label)
        layout.addWidget(self.progress_bar, stretch=0)
        self.set_state(ProgressState.NO_IMAGE)

    open_image_requested = QtCore.Signal()

    cancel_load_requested = QtCore.Signal()

    view_log_requested = QtCore.Signal()

    @QtCore.Slot()  # noqa
    def reset(self) -> None:
        self.progress_bar.reset()
        self.set_value(0)

    @QtCore.Slot(int)  # noqa
    def set_value(self, percent_complete: int) -> None:
        self.progress_bar.setValue(percent_complete)
        if percent_complete >= 100:
            self.set_state(ProgressState.IMAGE_COMPLETE)
        elif percent_complete > 0:
            self.set_state(ProgressState.IMAGE_LOADING)

    def set_state(self, state: ProgressState) -> None:
        if state == ProgressState.NO_IMAGE:
            self.open_button.show()
            self.cancel_button.hide()
            self.cancelled_button.hide()
            self.failed_button.hide()
            self.done_label.hide()
        elif state == ProgressState.IMAGE_LOADING:
            self.open_button.hide()
            self.cancel_button.show()
            self.cancelled_button.hide()
            self.failed_button.hide()
            self.done_label.hide()
        elif state == ProgressState.LOAD_CANCELLED:
            self.open_button.hide()
            self.cancel_button.hide()
            self.cancelled_button.show()
            self.failed_button.hide()
            self.done_label.hide()
        elif state == ProgressState.LOAD_FAILED:
            self.open_button.hide()
            self.cancel_button.hide()
            self.cancelled_button.hide()
            self.failed_button.show()
            self.done_label.hide()
        elif state == ProgressState.IMAGE_COMPLETE:
            self.open_button.hide()
            self.cancel_button.hide()
            self.cancelled_button.hide()
            self.failed_button.hide()
            self.done_label.show()
        else:
            assert False
