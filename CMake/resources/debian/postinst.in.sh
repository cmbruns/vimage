#!/bin/sh
set -e

update-mime-database /usr/share/mime

# Create symlink if missing
if [ ! -e /usr/local/bin/vimage ]; then
    ln -s /usr/local/vimage/vimage /usr/local/bin/vimage
fi
