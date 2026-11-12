#!/bin/bash
# The packaged Lastbook.app with the local AI: crash and restart, then the runner leaving with the app (quit and killed).
# Never packaged. Uses the Accessibility helper in mac_ask_check.py.
#   bash app/tests/mac_ai_lifecycle.sh DATA_FOLDER
set -u
HERE="$(dirname "$(/bin/realpath "$0")")"
ROOT="$(dirname "$(dirname "$HERE")")"
APPX="$(readlink "$ROOT/derived/app-build/mac/Lastbook.app")"
PY="$ROOT/derived/app-only-proof/mac/venv/bin/python"
D="$1"
OUT="$(mktemp -d)"
ax() { "$PY" -B "$HERE/mac_ask_check.py" "$PID" "$@"; }
must() {   # the same press until it lands: the page's accessibility tree fills in some seconds after the window shows
  for i in $(seq 1 20); do ax "$@" | grep -q "'err': 0" && return 0; sleep 1; done
  echo "   could not press: $*"; return 1
}
start() {
  "$APPX/Contents/MacOS/Lastbook" --data "$D" > /dev/null 2>&1 < /dev/null &
  PID=$!
  sleep 10
  PYTHONPATH="$HERE" "$PY" -B - "$PID" <<'EOF'
import sys, objc, mac_ax
f = {}
objc.loadBundleFunctions(mac_ax._b, f, [('AXUIElementSetAttributeValue', b'i^{__AXUIElement=}@@')])
f['AXUIElementSetAttributeValue'](mac_ax._f['AXUIElementCreateApplication'](int(sys.argv[1])), 'AXManualAccessibility', True)
EOF
  sleep 5     # WebKit builds the page's accessibility tree a few seconds after it is asked to
  must press "lastbook://app/#/ask"; sleep 2; must press "New chat"; sleep 2
}
answer() {   # presses a starter question, waits for sources or an error
  must button "$1"
  for i in $(seq 1 40); do
    sleep 3
    ax read > "$OUT/page.txt"
    if grep -q "Sources (" "$OUT/page.txt"; then echo "answered after ~$((i * 3)) s"; return 0; fi
    if grep -q "stopped unexpectedly\|could not start" "$OUT/page.txt"; then echo "error shown: $(grep -m1 -o 'The local AI[^|]*' "$OUT/page.txt")"; return 1; fi
  done
  echo "no answer"; return 2
}
runner() { pgrep -f "Contents/Frameworks/llm/lastbook-llm" || true; }

start
echo "1. crash while answering"
must button "fridge has been off"
for i in $(seq 1 60); do ax read | grep -q "Writing the answer" && break; sleep 0.5; done   # crash it while it writes, not while it loads
R=$(runner); [ -n "$R" ] && kill -9 $R && echo "   killed runner $R"
sleep 4
ax read | grep -m1 -o "The local AI stopped unexpectedly[^|]*" | sed 's/^/   shown: /'
echo "2. ask again in a new chat"
must press "New chat"; sleep 2
answer "generator safely" | sed 's/^/   /'
echo "3. quit the app while the model runs"
R=$(runner); echo "   runner before quit: ${R:-none}"
kill "$PID"; sleep 4
R2=$(runner); echo "   runner after quit: ${R2:-gone}"
echo "4. app killed outright while the model runs"
start
answer "toilets don" | sed 's/^/   /'
R=$(runner); echo "   runner before: ${R:-none}"
kill -9 "$PID"; sleep 4
R2=$(runner); echo "   runner after the app was killed: ${R2:-gone}"
rm -rf "$OUT"
