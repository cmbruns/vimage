import logging

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class LoggingQTextEdit(QtWidgets.QTextEdit):
    """
    TextEdit widget that populates itself with python logging messages
    """

    def __init__(self, parent):
        super().__init__(parent)
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
            formatter = logging.Formatter(
                "%(asctime)s.%(msecs)03d[%(levelname)-.1s]%(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
            self.setFormatter(formatter)
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
