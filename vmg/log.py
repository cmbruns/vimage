import logging
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

logging.basicConfig(
    level=logging.DEBUG,
    format=logging.BASIC_FORMAT,
)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


class LogSignaller(QtCore.QObject):
    log = QtCore.Signal(str)


class LogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
        self.signaller = LogSignaller()
        root_logger.addHandler(self)

    def emit(self, record):
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


class QTextEditLogger(QtWidgets.QTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.handler = LogHandler()
        self.handler.signaller.log.connect(self.append_text, Qt.QueuedConnection)  # noqa
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

    @QtCore.Slot(str)  # noqa
    def append_text(self, msg: str):
        self.append(msg)
        self.moveCursor(QtGui.QTextCursor.End)


class LogWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("vimage log")
        self.text_edit = QTextEditLogger(self)
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


class LoggerWriter(object):
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


class StdIoRedirector(object):
    """
    Sends stdout and sterr to python logging system
    """
    def __init__(self, stdout_level=logging.INFO, stderr_level=logging.ERROR):
        self._cached_stdout = sys.stdout
        self._cached_stderr = sys.stderr
        sys.stdout = self._writer("STDOUT", stdout_level)
        sys.stderr = self._writer("STDERR", stderr_level)

    @staticmethod
    def _writer(logger_name: str, level: int) -> LoggerWriter:
        lgr: logging.Logger = logging.getLogger(logger_name)
        if level == logging.DEBUG:
            fn = lgr.debug
        elif level == logging.INFO:
            fn = lgr.info
        elif level == logging.WARNING:
            fn = lgr.warning
        elif level == logging.ERROR:
            fn = lgr.error
        elif level == logging.CRITICAL:
            fn = lgr.critical
        return LoggerWriter(fn)

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        sys.stdout = self._cached_stdout
        sys.stderr = self._cached_stderr


def main():
    app = QtWidgets.QApplication(sys.argv)
    log_window = LogWindow()
    log_window.text_edit.setPlainText(
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
    logger.debug("Oh no! A bug!")
    logger.info("just saying")
    logger.warning("be careful")
    logger.error("problem")
    print("Just printing (stdout)")
    print("printing to stderr", file=sys.stderr)
    log_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
