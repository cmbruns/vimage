from io import StringIO

import logging
import sys
import traceback

from collections import namedtuple

fake_tb = namedtuple("fake_tb", ("tb_frame", "tb_lasti", "tb_lineno", "tb_next"))
logger = logging.getLogger(__name__)


class ExceptHook(object):
    def __init__(self):
        self._old_except_hook = sys.excepthook
        sys.excepthook = self.except_hook

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        sys.excepthook = self._old_except_hook

    def except_hook(self, exc_type, exc_value, exc_traceback):
        enriched_tb = self._add_missing_frames(exc_traceback) if exc_traceback else exc_traceback
        # Note: sys.__excepthook__(...) would not work here.
        # We need to use print_exception(...):
        file_string = StringIO()
        traceback.print_exception(exc_type, exc_value, enriched_tb, file=file_string)
        logger.error(file_string.getvalue())

    @staticmethod
    def _add_missing_frames(exc_traceback):
        result = fake_tb(
            exc_traceback.tb_frame,
            exc_traceback.tb_lasti,
            exc_traceback.tb_lineno,
            exc_traceback.tb_next
        )
        frame = exc_traceback.tb_frame.f_back
        while frame:
            result = fake_tb(frame, frame.f_lasti, frame.f_lineno, result)
            frame = frame.f_back
        return result


__all__ = [
    "ExceptHook"
]
