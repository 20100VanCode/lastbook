#!/bin/bash
# Logs every internet socket a running Lastbook (and its children) holds, every 2 s, until it exits or STOP appears.
# Never packaged.   bash app/tests/mac_net_watch.sh PID OUT_FILE      (touch OUT_FILE.stop to end it)
PID="$1"; OUT="$2"
: > "$OUT"
while kill -0 "$PID" 2>/dev/null && [ ! -e "$OUT.stop" ]; do
  pids="$PID $(pgrep -P "$PID" | tr '\n' ' ')"
  for p in $pids; do
    lsof -nP -a -p "$p" -i 2>/dev/null | tail -n +2 | sed "s/^/$(date +%T) /" >> "$OUT"
  done
  sleep 2
done
# bytes in and out over the whole life of the process, as nettop counts them
nettop -P -L 1 -x -p "$PID" -J bytes_in,bytes_out 2>/dev/null >> "$OUT"
echo "$(date +%T) watch ended" >> "$OUT"
