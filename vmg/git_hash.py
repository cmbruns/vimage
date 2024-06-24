"""
Read git hash information from a pre-existing text file not tracked by git.
"""

import pkg_resources

vimage_git_hash = "<unknown>"

try:
    file_name = pkg_resources.resource_filename("vmg", "git_hash.txt")
    with open(file_name) as fh:
        contents = fh.read()
    vimage_git_hash = contents.split()[2]
except FileNotFoundError:
    pass


__all__ = [
    "vimage_git_hash"
]
