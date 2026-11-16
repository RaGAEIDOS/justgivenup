#!/bin/sh
# JustGivenUp! — adds the apt repository and installs the package.
#
#   curl -fsSL https://ragaeidos.website/justgivenup/install.sh | sudo sh
#
# Run as root. Everything after this runs as a normal apt install.
set -e

REPO_FILE="/etc/apt/sources.list.d/justgivenup.list"

echo "=== JustGivenUp! Guardian — apt repository setup ==="
echo "Writing $REPO_FILE ..."
cat > "$REPO_FILE" <<'EOF'
deb [arch=amd64 trusted=yes] https://ragaeidos.website/justgivenup stable main
EOF

echo "Updating package indexes (expected: 'no InRelease' is fine — trusted=yes) ..."
apt-get update || apt-get update -o Acquire::AllowInsecureRepositories=true

echo "Installing justgivenup ..."
apt-get install -y justgivenup

echo ""
echo "Done! Open the dashboard:"
echo "  http://127.0.0.1:8081"
echo ""
echo "Install the browser extension (optional, recommended):"
echo "  Chrome/Edge/Brave : chrome://extensions → Developer mode → Load unpacked"
echo "                      /usr/lib/justgivenup/justgivenup/extension"
echo "  Firefox           : about:addons → Install Add-on From File"
echo "                      /usr/lib/justgivenup/justgivenup/extension/justgivenup.xpi"
