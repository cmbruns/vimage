import time


class Performance(object):
    def __init__(self, indent=0, message="", do_report=True):
        self.indent = indent
        self.begin = time.time()
        self.message = message
        self.do_report = do_report

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        end = time.time()
        _elapsed = end - self.begin
        if self.do_report:
            print(f"{self.indent * ' '}{self.message} elapsed time = {_elapsed * 1000:.1f} ms")
