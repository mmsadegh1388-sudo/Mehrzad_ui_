#!/usr/bin/env bash
set -euo pipefail
DIR="${MEHRZAD_INSTALL_DIR:-/opt/mehrzad_ui}"
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
[[ -f "$(dirname "$0")/app.py" && -f "$(dirname "$0")/index.html" ]] || { echo 'Run from extracted project directory'; exit 1; }
install -d -o root -g root -m 0755 "$DIR"
install -d -o root -g root -m 0700 "$DIR/data"
install -o root -g root -m 0644 "$(dirname "$0")/app.py" "$DIR/app.py"
install -o root -g root -m 0644 "$(dirname "$0")/index.html" "$DIR/index.html"
install -o root -g root -m 0644 "$(dirname "$0")/README.md" "$DIR/README.md"
echo "Prototype files installed in $DIR. No VPN engine or public service configured."
echo "Initialize an administrator and run locally; see README.md."
