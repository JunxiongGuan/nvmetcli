#!/bin/sh
#
# Bump the version and cut a release.  Can't be called release.sh because
# that would conflict with the make release rule in the makefile.
#

VER=$1

set -e
set +x

if [ -z "$VER" ]; then
   echo "usage: $0 version" >&2
   exit 1
fi

sed -i "s/version =.*,/version = $VER,/" setup.py
git add setup.py
git commit -m "bump version to v$VER"

git tag -s "v$VER" -m "nvmetcli release v$VER"

make release
(cd dist && gpg --armor --detach-sign nvmetcli-$VER.tar.gz)
