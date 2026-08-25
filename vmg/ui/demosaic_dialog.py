from PySide6 import QtCore
from PySide6.QtWidgets import QButtonGroup, QDialog

from vmg.interfaces import DemosaicMethod
from vmg.ui.ui_demosaic_dialog import Ui_Dialog


class DemosaicDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        method_group = QButtonGroup(self)
        for button in [
            self.ui.radioButtonLanczos7x7,
            self.ui.radioButtonMalvar_He_Cutler_5x5,
            self.ui.radioButtonLanczos_5x5_Green_Median_Chroma,
            self.ui.radioButtonBilinear_3x3,
        ]:
            method_group.addButton(button)
        self.ui.checkBoxShow_CFA_Colors.toggled.connect(self.show_cfa_colors_toggled)

    def closeEvent(self, event):
        event.ignore()   # prevent destruction
        self.hide()      # just hide the window

    demosaic_method_changed = QtCore.Signal(DemosaicMethod)
    show_cfa_colors_toggled = QtCore.Signal(bool)
