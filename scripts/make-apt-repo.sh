#!/bin/sh
# Generate the gh-pages APT repository (and landing page) tree.
#
# Input:  dist/justgivenup_<ver>_all.deb   (run scripts/build-deb.sh first)
# Output: site-build/  (ready to publish as the gh-pages branch root)
#
# Users then run:
#   echo "deb [trusted=yes] https://ragaeidos.website/justgivenup stable main" \
#     | sudo tee /etc/apt/sources.list.d/justgivenup.list
#   sudo apt update && sudo apt install justgivenup
set -e
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/justgivenup/__init__.py | head -1)
DEB="justgivenup_${VERSION}_all.deb"

if [ ! -f "dist/$DEB" ]; then
    echo "missing dist/$DEB — run scripts/build-deb.sh first" >&2
    exit 1
fi

SITE="site-build"
POOL_REL="pool/main/j/justgivenup"
DIST_REL="dists/stable"

rm -rf "$SITE"
mkdir -p "$SITE/$POOL_REL"
mkdir -p "$SITE/$DIST_REL/main/binary-amd64"
mkdir -p "$SITE/$DIST_REL/main/binary-all"
mkdir -p "$SITE/extensions"

cp "dist/$DEB" "$SITE/$POOL_REL/"

# Packages indexes (amd64 is the primary arch dir; "all" mirrors it so
# Architecture: all packages are found on every multiarch setup too).
# NOTE: run from inside the site tree so Filename: is repo-relative.
(cd "$SITE" && dpkg-scanpackages --multiversion pool /dev/null \
    > dists/stable/main/binary-amd64/Packages 2>/dev/null)
cp "$SITE/$DIST_REL/main/binary-amd64/Packages" \
   "$SITE/$DIST_REL/main/binary-all/Packages"
gzip -9cn "$SITE/$DIST_REL/main/binary-amd64/Packages" \
    > "$SITE/$DIST_REL/main/binary-amd64/Packages.gz"
gzip -9cn "$SITE/$DIST_REL/main/binary-all/Packages" \
    > "$SITE/$DIST_REL/main/binary-all/Packages.gz"

# Release file (verified contents; apt trusts it via [trusted=yes])
apt-ftparchive \
  -o "APT::FTPArchive::Release::Origin=JustGivenUp! Guardian" \
  -o "APT::FTPArchive::Release::Label=JustGivenUp!" \
  -o "APT::FTPArchive::Release::Suite=stable" \
  -o "APT::FTPArchive::Release::Codename=stable" \
  -o "APT::FTPArchive::Release::Architectures=amd64 all" \
  -o "APT::FTPArchive::Release::Components=main" \
  release "$SITE/$DIST_REL" > "$SITE/$DIST_REL/Release"

# landing page + bootstrap script
cp site/index.html "$SITE/index.html"
cp site/install.sh "$SITE/install.sh"
chmod +x "$SITE/install.sh"
touch "$SITE/.nojekyll"

# extension bundles for manual download
for z in dist/justgivenup-chrome-*.zip dist/justgivenup-firefox-*.xpi; do
    [ -f "$z" ] && cp "$z" "$SITE/extensions/"
done

echo "apt repository ready in: $SITE"
echo "  add the repo with:"
echo '  echo "deb [trusted=yes] https://ragaeidos.website/justgivenup stable main" | sudo tee /etc/apt/sources.list.d/justgivenup.list'
echo "  sudo apt update && sudo apt install justgivenup"
ls -R "$SITE" | head -30
