import inspect
import logging
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class LoggingQTextEdit(QtWidgets.QTextEdit):
    """
    TextEdit widget that populates itself with python logging messages
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setFont({"Consolas"})
        self.handler = self.LogHandler()
        self.handler.signaller.log.connect(self.append_text, Qt.QueuedConnection)  # noqa
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

    @QtCore.Slot(str)  # noqa
    def append_text(self, msg: str):
        self.append(msg)
        self.moveCursor(QtGui.QTextCursor.End)
        self.moveCursor(QtGui.QTextCursor.StartOfLine)

    class LogHandler(logging.Handler):
        """logging handler that emits a Qt signal when a message arrives"""

        def __init__(self):
            super().__init__()
            # self.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
            self.signaller = self.LogSignaller()
            logging.getLogger().addHandler(self)

        def emit(self, record: logging.LogRecord) -> None:
            """
            If a formatter is specified, it is used to format the record.
            The record is then written to the stream followed by terminator.
            If exception information is present, it is formatted using
            traceback.print_exception() and appended to the stream.

            :param record: Contains all the information pertinent to the event being logged.
            :return: None
            """
            msg = self.format(record)
            if record.levelno == logging.WARNING:
                emoji = u"\u26A0\ufe0f"  # Unicode for the warning emoji
                text = f"{emoji} {msg}"
            elif record.levelno == logging.INFO:
                emoji = u"\U00002705"  # Unicode for the check mark emoji
                text = f"{emoji} {msg}"
            elif record.levelno == logging.DEBUG:
                emoji = u"\U0001f41e"  # Unicode for the spider emoji
                text = f"{emoji} {msg}"
            elif record.levelno == logging.ERROR:
                emoji = u"\u274c"  # Unicode for the red circle emoji
                text = f"{emoji} {msg}"
            else:
                text = msg
            self.signaller.log.emit(text)  # noqa

        class LogSignaller(QtCore.QObject):
            """
            Signalling part of LogHandler,
            for composition of classes that both have "emit()" methods.
            """
            log = QtCore.Signal(str)


class LogWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("vimage log")
        self.text_edit = LoggingQTextEdit(self)
        # formatter = logging.Formatter("%(asctime)s:%(name)s:%(levelname)s:%(message)s")
        formatter = logging.Formatter("[%(levelname)-.1s]%(name)s: %(message)s")
        self.text_edit.handler.setFormatter(formatter)
        cursor = QtGui.QTextCursor(self.text_edit.document())
        cursor.select(QtGui.QTextCursor.Document)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
        self.dialog_geometry = None

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        if self.dialog_geometry is not None:
            self.setGeometry(self.dialog_geometry)
        logger.info("vimage log window shown")

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.dialog_geometry = self.geometry()
        self.hide()


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
    log_window = LogWindow()
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
