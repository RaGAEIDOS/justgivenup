#!/bin/sh
# Build the justgivenup Debian package from the checked-in packaging/deb
# skeleton + the Python app, web UI, extension and blocklists.
#
# Outputs:  dist/justgivenup_<VERSION>_all.deb
set -e
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/justgivenup/__init__.py | head -1)
[ -n "$VERSION" ] || { echo "could not read VERSION from app/justgivenup/__init__.py"; exit 1; }

DEB_NAME="justgivenup_${VERSION}_all.deb"
OUT_DIR="dist"
STAGE="$(mktemp -d /tmp/jgu-deb-stage.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

echo "== justgivenup $VERSION =="
echo "stage: $STAGE"

# 1. packaging skeleton (DEBIAN/*, systemd units, wrapper, desktop, icons)
cp -a packaging/deb/. "$STAGE/"
# inject the current VERSION into the control file
sed -i "s/^Version: .*/Version: $VERSION/" "$STAGE/DEBIAN/control"

# 2. python package (code + web UI + extension + blocklists + hooks)
PKG="$STAGE/usr/lib/justgivenup/justgivenup"
mkdir -p "$PKG/data"
cp app/justgivenup/*.py "$PKG/"
cp -a app/web "$PKG/web"
cp -a extension "$PKG/extension"
# Firefox XPI: same sources, Firefox manifest variant
XPI_TMP="$STAGE/xpi-build"
mkdir -p "$XPI_TMP"
cp -a extension/. "$XPI_TMP/"
cp extension/manifest.firefox.json "$XPI_TMP/manifest.json"
rm -f "$XPI_TMP/manifest.firefox.json"
cp extension/rules.firefox.json "$XPI_TMP/rules.json"
rm -f "$XPI_TMP/rules.firefox.json"
(cd "$XPI_TMP" && zip -qr "$PKG/extension/justgivenup.xpi" .)
rm -rf "$XPI_TMP"
cp data/blocklist_full.txt data/blocklist_core.txt "$PKG/data/"
mkdir -p "$PKG/hooks"
cp app/justgivenup/hooks/*.py "$PKG/hooks/"

# 3. correctness guards
[ -f "$PKG/data/blocklist_full.txt" ] || { echo "missing blocklist_full.txt"; exit 1; }
[ -f "$PKG/extension/rules.json" ] || { echo "missing extension rules.json"; exit 1; }
[ -f "$PKG/data/blocklist_core.txt" ] || { echo "missing blocklist_core.txt"; exit 1; }
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"
chmod 755 "$STAGE/usr/bin/justgivenup"
chmod -R a+rX "$STAGE"

# 4. build
mkdir -p "$OUT_DIR"
dpkg-deb --build "$STAGE" "$OUT_DIR/$DEB_NAME"
echo "built: $OUT_DIR/$DEB_NAME"
du -h "$OUT_DIR/$DEB_NAME" | cut -f1
