import logging
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class LogSignaller(QtCore.QObject):
    log = QtCore.Signal(str)


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.signaller = LogSignaller()
        logging.getLogger().addHandler(self)
        logging.getLogger().setLevel(logging.DEBUG)

    def emit(self, record):
        msg = self.format(record)
        self.signaller.log.emit(msg)


class QTextEditLogger(QtWidgets.QTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.handler = LogHandler()
        self.handler.signaller.log.connect(self.append, Qt.QueuedConnection)
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)


class LogDialog(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.text_edit = QTextEditLogger(self)
        self.text_edit.setPlainText(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Fusce malesuada lacus nec sapien hendrerit mollis. Etiam "
            "euismod consequat magna sed ornare. Donec dapibus aliquet "
            "turpis eget gravida. Morbi porttitor orci pharetra magna "
            "ultrices, vel facilisis mauris ullamcorper. Curabitur a "
            "fringilla arcu. Mauris vulputate sodales blandit.\n"
            "Nam pellentesque volutpat est vitae ultrices. Nam at augue "
            "quis massa porttitor suscipit et ac neque.\n"
            "Cras dolor risus, lobortis nec nisl nec, suscipit iaculis "
            "tellus. Nulla non bibendum elit, ut gravida lacus.\n"
            "Hic rerum voluptas voluptatem.\n"
            "Ut expedita unde eum molestias voluptatem aut dignissimos dolor."
        )

        # Set left margin and negative text indent
        fmt = QtGui.QTextBlockFormat()
        fmt.setLeftMargin(40)
        fmt.setTextIndent(-40)
        cursor = QtGui.QTextCursor(self.text_edit.document())
        cursor.select(QtGui.QTextCursor.Document)
        cursor.mergeBlockFormat(fmt)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.text_edit)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dialog = LogDialog()
    dialog.show()
    sys.exit(app.exec())