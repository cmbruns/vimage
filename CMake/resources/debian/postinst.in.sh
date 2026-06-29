#!/bin/sh
set -e

update-mime-database /usr/share/mime

# Create symlink if missing
if [ ! -e @CMAKE_INSTALL_PREFIX@/bin/vimage ]; then
    ln -s @CMAKE_INSTALL_PREFIX@/vimage/vimage @CMAKE_INSTALL_PREFIX@/bin/vimage
fi
