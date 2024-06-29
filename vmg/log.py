import inspect
import logging
import sys

from PySide6 import QtWidgets, QtGui, QtCore

from vmg.ui_log import Ui_LogDialog

logger = logging.getLogger(__name__)


class LogDialog(Ui_LogDialog, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        cursor = QtGui.QTextCursor(self.text_edit.document())
        cursor.select(QtGui.QTextCursor.Document)
        self.dialog_geometry = None

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.dialog_geometry = self.geometry()
        self.hide()

    @QtCore.Slot()
    def on_saveLogButton_clicked(self):
        file_name, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save vimage log to file",
            "vimage_log.txt",
            "Text files (*.txt)"
        )
        if len(file_name) > 0:
            with open(file_name, "w", encoding="utf-8") as fh:
                text = self.text_edit.toPlainText()
                fh.write(text)

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        if self.dialog_geometry is not None:
            self.setGeometry(self.dialog_geometry)
        logger.debug("vimage log window shown")

    _levels = {
        "Critical": logging.CRITICAL,
        "Error": logging.ERROR,
        "Warning": logging.WARNING,
        "Info": logging.INFO,
        "Debug": logging.DEBUG,
    }

    @QtCore.Slot(str)
    def on_comboBox_currentTextChanged(self, text: str):
        level = self._levels[text]
        logging.getLogger().setLevel(level)  # Adjust root logger


class StdIoRedirector(object):
    """
    ** Run this AFTER you load the logger **
    Sends stdout and sterr to python logging system.
    """
    def __init__(self, stdout_level=logging.INFO, stderr_level=logging.ERROR):
        self._cached_stdout = sys.stdout
        self._cached_stderr = sys.stderr
        sys.stdout = self._writer("STDOUT", stdout_level)
        sys.stderr = self._writer("STDERR", stderr_level)

    def _writer(self, logger_name: str, level: int) -> "LoggerWriter":
        lgr: logging.Logger = logging.getLogger(logger_name)
        if level == logging.DEBUG:
            fn = lgr.debug
        elif level == logging.INFO:
            fn = lgr.info
        elif level == logging.WARNING:
            fn = lgr.warning
        elif level == logging.ERROR:
            fn = lgr.error
        else:  # level == logging.CRITICAL:
            fn = lgr.critical
        return self.LoggerWriter(fn)

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        sys.stdout = self._cached_stdout
        sys.stderr = self._cached_stderr

    class LoggerWriter(object):
        """
        Helper class for StdIoRedirector
        """
        def __init__(self, writer):
            self._writer = writer
            self._msg = ""

        def write(self, message):
            self._msg = self._msg + message
            while "\n" in self._msg:
                pos = self._msg.find("\n")
                self._writer(self._msg[:pos])
                self._msg = self._msg[pos+1:]

        def flush(self):
            if self._msg != "":
                self._writer(self._msg)
                self._msg = ""


def exercise_log_window():
    app = QtWidgets.QApplication(sys.argv)
    log_window = LogDialog()
    log_window.text_edit.setPlainText(inspect.cleandoc(
        """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Fusce malesuada lacus nec sapien hendrerit mollis. Etiam 
        euismod consequat magna sed ornare. Donec dapibus aliquet 
        turpis eget gravida. Morbi porttitor orci pharetra magna 
        ultrices, vel facilisis mauris ullamcorper. Curabitur a 
        fringilla arcu. Mauris vulputate sodales blandit.
        Nam pellentesque volutpat est vitae ultrices. Nam at augue 
        quis massa porttitor suscipit et ac neque.
        Cras dolor risus, lobortis nec nisl nec, suscipit iaculis 
        tellus. Nulla non bibendum elit, ut gravida lacus.
        Hic rerum voluptas voluptatem.
        Ut expedita unde eum molestias voluptatem aut dignissimos dolor.
        """  # noqa
    ))
    logger.debug("Oh no! A bug!")
    logger.info("just saying")
    logger.warning("be careful")
    logger.error("problem")
    print("Just printing (stdout)")
    print("printing to stderr", file=sys.stderr)
    log_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=logging.BASIC_FORMAT)
    logger = logging.getLogger(__name__)
    with StdIoRedirector():  # AFTER creating logger
        exercise_log_window()


