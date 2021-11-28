# https://stackoverflow.com/a/4623518/146574

import re


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r"(\d+)", str(s))]


__all__ = [
    "natural_sort_key",
    ]
