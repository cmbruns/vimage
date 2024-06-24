"""
Read git hash information from a pre-existing text file not tracked by git.
"""

import os
import sys

vimage_git_hash = "<unknown>"

try:
    # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)
    else:
        application_path = os.getcwd()

    config_path = f"{application_path}/git_hash.txt"
    with open(config_path) as fh:
        contents = fh.read()
    vimage_git_hash = contents.split()[2]
except FileNotFoundError:
    pass


__all__ = [
    "vimage_git_hash"
]
