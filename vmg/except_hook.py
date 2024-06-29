import sys
import traceback

from collections import namedtuple


def except_hook(exc_type, exc_value, exc_tb):
    enriched_tb = _add_missing_frames(exc_tb) if exc_tb else exc_tb
    # Note: sys.__excepthook__(...) would not work here.
    # We need to use print_exception(...):
    traceback.print_exception(exc_type, exc_value, enriched_tb)


def _add_missing_frames(tb):
    result = fake_tb(tb.tb_frame, tb.tb_lasti, tb.tb_lineno, tb.tb_next)
    frame = tb.tb_frame.f_back
    while frame:
        result = fake_tb(frame, frame.f_lasti, frame.f_lineno, result)
        frame = frame.f_back
    return result


fake_tb = namedtuple("fake_tb", ("tb_frame", "tb_lasti", "tb_lineno", "tb_next"))

sys.excepthook = except_hook
