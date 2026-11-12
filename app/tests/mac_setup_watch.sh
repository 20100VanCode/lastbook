#!/bin/bash
# Watches the setup screen of a running packaged Lastbook.app through Accessibility until it opens the library or fails.
# Never packaged.  bash app/tests/mac_setup_watch.sh PID [press-first]
HERE="$(dirname "$(/bin/realpath "$0")")"
ROOT="$(dirname "$(dirname "$HERE")")"
PY="$ROOT/derived/app-only-proof/mac/venv/bin/python"
PID="$1"
[ -n "${2:-}" ] && "$PY" -B "$HERE/mac_ask_check.py" "$PID" button "$2"
t0=$(date +%s); last=""
while kill -0 "$PID" 2>/dev/null; do
  page="$("$PY" -B "$HERE/mac_ask_check.py" "$PID" read 2>/dev/null)"
  now="$(echo "$page" | grep -E "AXHeading|of [0-9.]+ [GM]B|Checking|Unpacking|Finishing|could not|failed|error|Ask the library|What do you need" | grep -v "^roles" | sed 's/^ *//' | head -6 | tr '\n' ' ' | cut -c1-300)"
  if [ "$now" != "$last" ]; then echo "$(( $(date +%s) - t0 ))s  $now"; last="$now"; fi
  echo "$page" | grep -q "What do you need?\|AXWebArea: Lastbook | lastbook://app/#" && { echo "library open"; break; }
  echo "$page" | grep -qiE "AXHeading: .*(could not|failed|went wrong)" && { echo "FAILED"; break; }
  sleep 15
done
