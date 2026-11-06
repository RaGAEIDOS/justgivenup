#!/bin/sh
# Package the browser extension bundles into dist/.
#
#   dist/justgivenup-chrome-<ver>.zip   Chrome/Edge/Brave/Vivaldi (unpacked-dir zip)
#   dist/justgivenup-firefox-<ver>.xpi  Firefox (XPI with gecko manifest)
set -e
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/justgivenup/__init__.py | head -1)
mkdir -p dist

CHROME_ZIP="dist/justgivenup-chrome-${VERSION}.zip"
FIREFOX_XPI="dist/justgivenup-firefox-${VERSION}.xpi"

(cd extension && zip -qr "../$CHROME_ZIP" . -x 'manifest.firefox.json')
echo "chrome:  $CHROME_ZIP"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/jgu-xpi.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
cp -a extension/. "$TMP/"
cp extension/manifest.firefox.json "$TMP/manifest.json"
rm -f "$TMP/manifest.firefox.json"
# Firefox DNR: ship the firefox-only ruleset (no `transform` rules —
# Firefox rejects the whole set when one is present)
cp extension/rules.firefox.json "$TMP/rules.json"
rm -f "$TMP/rules.firefox.json"
(cd "$TMP" && zip -qr "$ROOT/$FIREFOX_XPI" .)
echo "firefox: $FIREFOX_XPI"

ls -la dist/justgivenup-chrome-* dist/justgivenup-firefox-*
