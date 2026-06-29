#!/bin/sh
set -e

# Remove symlink if it exists and points to our binary
if [ -L @CMAKE_INSTALL_PREFIX@/bin/vimage ]; then
    rm @CMAKE_INSTALL_PREFIX@/bin/vimage
fi

update-mime-database /usr/share/mime
