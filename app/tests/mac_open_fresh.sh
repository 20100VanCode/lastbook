#!/bin/bash
# Opens the packaged Lastbook.app as a different person: HOME is the given folder. Turns on web accessibility, prints the pid.
# Never packaged.   bash app/tests/mac_open_fresh.sh HOME_FOLDER
HERE="$(dirname "$(/bin/realpath "$0")")"
ROOT="$(dirname "$(dirname "$HERE")")"
APPX="$(readlink "$ROOT/derived/app-build/mac/Lastbook.app")"
PY="$ROOT/derived/app-only-proof/mac/venv/bin/python"
H="$1"
mkdir -p "$H/Downloads" "$H/Documents" "$H/Desktop"
HOME="$H" "$APPX/Contents/MacOS/Lastbook" >> "$H/stdout.txt" 2>&1 < /dev/null &
PID=$!
sleep 10
PYTHONPATH="$HERE" "$PY" -B - "$PID" <<'EOF'
import sys, objc, mac_ax
f = {}
objc.loadBundleFunctions(mac_ax._b, f, [('AXUIElementSetAttributeValue', b'i^{__AXUIElement=}@@')])
f['AXUIElementSetAttributeValue'](mac_ax._f['AXUIElementCreateApplication'](int(sys.argv[1])), 'AXManualAccessibility', True)
EOF
sleep 6
echo "$PID"
