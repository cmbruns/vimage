import time


class ElapsedTime(object):
    def __init__(self, indent=0, message="", do_report=True):
        self.indent = indent
        self.begin = time.time()
        self.message = message
        self.do_report = do_report

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        if self.do_report:
            print(f"{self.indent * ' '}{self.message} elapsed time = {str(self)}")

    def __str__(self):
        end = time.time()
        _elapsed = end - self.begin
        return f"{_elapsed * 1000:.1f} ms"
