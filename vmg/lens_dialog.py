from PySide6 import QtWidgets

from vmg.ui_lens_parameters import Ui_Dialog


class LensDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

    def closeEvent(self, event):
        event.ignore()   # prevent destruction
        self.hide()      # just hide the window
