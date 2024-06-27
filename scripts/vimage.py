"""
file vimage.py

Launches the vimage application.
This python script is the primary entry point for pyinstaller-based packages.
"""

# Hack to make it work with pyinstaller
try:
    from OpenGL.platform import win32  # required
except AttributeError:
    pass

try:
    from OpenGL.arrays import (
        numpymodule,  # required
        ctypesarrays,  # required
        strings,  # required
    )
except AttributeError:
    pass

from vmg import VimageApp

VimageApp()
